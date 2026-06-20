from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from alab import cli
from alab.auth import create_credential, write_token
from alab.context import path_hash, write_marker
from alab.dashboard import (
    DASHBOARD_TOKEN_HEADER,
    cmd_dashboard,
    read_project_detail,
    read_summary,
    read_system,
)
from alab.home import Home
from alab.ids import new_id
from alab.service_models import GlobalOptions, Request

_URL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _urlopen(request: str | urllib.request.Request):
    return _URL_OPENER.open(request)


def _field_map(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    return fields


def _init_home(tmp_path: Path, capsys) -> tuple[Home, str]:
    home = Home(tmp_path / "home")
    assert cli.run(["--home", str(home.path), "auth", "init"]) == 0
    root_key = _field_map(capsys.readouterr().out)["root key"]
    return home, root_key


def _now() -> str:
    return "2026-05-24T00:00:00Z"


def _seed_dashboard_data(home: Home) -> dict[str, str]:
    project_id = "proj-dashboard-AAAAAAAAAAAAAAAAAAAAAA"
    source_id = "src-dashboard-aaaaaaaaaaaaaaaa"
    exp_id = "exp-dashboard-AAAAAAAAAAAAAAAAAAAAAA"
    run_id = "run-dashboard-AAAAAAAAAAAAAAAAAAAAAA"
    log_id = "log-dashboard-AAAAAAAAAAAAAAAAAAAAAA"
    artifact_id = "art-dashboard-AAAAAAAAAAAAAAAAAAAAAA"
    validation_id = "val-dashboard-aaaaaaaaaaaaaaaa"
    secret_value_id = "sec-dashboard-aaaaaaaaaaaaaaaa"
    audit_id = "aud-dashboard-aaaaaaaaaaaaaaaa"
    config = {
        "schema_version": 1,
        "project": {
            "name": "Dashboard Project",
            "task": "Inspect local dashboard data",
            "goal": "Show a read-only root dashboard",
            "allow_public_exp_create": True,
        },
        "source": {"default_source_ref": f"alab/source/{source_id}"},
        "public_source_import": {
            "enabled": True,
            "max_files": 100000,
            "max_total_bytes": 1073741824,
            "max_file_bytes": 104857600,
        },
        "mutable": {"include": ["**"], "exclude": []},
        "visibility": {"scope": "same_project", "experiment_ids": []},
        "metrics": {
            "reference": [
                {
                    "name": "latency_ms",
                    "label": "Latency",
                    "direction": "minimize",
                    "unit": "ms",
                },
                {"name": "coverage", "label": "Coverage", "direction": "maximize"},
            ]
        },
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "sanitized",
            "command": [sys.executable, "-c", "print('ok')"],
            "shell": None,
            "image": None,
            "dockerfile": None,
            "context": None,
            "network": "default",
            "build_args": {},
            "target": None,
            "platform": None,
            "user": None,
            "cpus": None,
            "memory_mb": None,
            "harbor_task_ref": None,
            "skydiscover_task_ref": None,
            "program_path": ".",
        },
        "reward": {
            "type": "exit_code",
            "direction": "maximize",
            "primary_metric": "reward",
            "path": None,
            "pattern": None,
        },
        "artifacts": {
            "globs": [],
            "per_file_limit_bytes": 10485760,
            "per_run_limit_bytes": 104857600,
        },
        "logs": {"stdout_limit_bytes": 10485760, "stderr_limit_bytes": 10485760},
        "git": {"author_name": "ALab", "author_email": "alab@local"},
        "env": {"VISIBLE_ENV": "shown"},
        "secret_env": {
            "API_TOKEN": {
                "secret_value_id": secret_value_id,
                "fingerprint": "hmac-sha256:dashboard",
            }
        },
    }
    artifact_store = home.projects_path / project_id / "artifacts"
    log_rel = "logs/hidden.log"
    artifact_rel = "blobs/report.txt"
    (artifact_store / "logs").mkdir(parents=True)
    (artifact_store / "blobs").mkdir(parents=True)
    (artifact_store / log_rel).write_text("hidden diagnostic log\n", encoding="utf-8")
    (artifact_store / artifact_rel).write_text("artifact preview text\n", encoding="utf-8")
    feedback_dir = home.feedback_path / "fb-dashboard"
    feedback_dir.mkdir(parents=True)
    (feedback_dir / "metadata.json").write_text(
        json.dumps({"feedback_id": "fb-dashboard", "kind": "question", "title": "Dashboard?", "created_at": _now()}),
        encoding="utf-8",
    )
    (feedback_dir / "body.md").write_text("Can the dashboard show all root data?", encoding="utf-8")
    with sqlite3.connect(home.db_path) as conn:
        conn.execute(
            """
            INSERT INTO projects(project_id, status, pre_archive_status, canonical_repo_path, control_path,
              secret_fingerprint_key, latest_attempted_config_version, active_valid_config_version,
              active_validation_id, created_at, updated_at, archived_at)
            VALUES (?, 'valid', NULL, ?, ?, ?, 1, 1, ?, ?, ?, NULL)
            """,
            (project_id, str(home.projects_path / project_id / "repo.git"), str(home.project_workspaces_path / project_id), b"x" * 32, validation_id, _now(), _now()),
        )
        conn.execute(
            """
            INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
              baseline_required, validation_status, inherited_from_validation_id, created_at,
              created_by_credential_id)
            VALUES (?, 1, ?, 'sha256:dashboard', 0, 'passed', NULL, ?, NULL)
            """,
            (project_id, json.dumps(config, sort_keys=True, separators=(",", ":")), _now()),
        )
        conn.execute(
            """
            INSERT INTO secret_values(secret_value_id, project_id, name, value, fingerprint, created_at,
              created_by_credential_id, replaced_at)
            VALUES (?, ?, 'API_TOKEN', 'RAW_SECRET_SHOULD_NOT_LEAK', 'hmac-sha256:dashboard', ?, NULL, NULL)
            """,
            (secret_value_id, project_id, _now()),
        )
        conn.execute(
            """
            INSERT INTO sources(source_id, project_id, name, name_slug, source_ref, source_commit,
              tree_hash, status, origin_metadata_json, created_at, archived_at)
            VALUES (?, ?, 'source', 'source', ?, 'abc123', 'alab-tree-sha256-v1:abc', 'active',
              '{"schema_version":1}', ?, NULL)
            """,
            (source_id, project_id, f"alab/source/{source_id}", _now()),
        )
        conn.execute(
            """
            INSERT INTO project_validations(validation_id, project_id, config_version, source_ref,
              source_commit, status, exit_code, reward_value, reward_parse_status, archive_status,
              archived_at, unarchived_at, started_at, ended_at, record_json)
            VALUES (?, ?, 1, ?, 'abc123', 'passed', 0, 1.0, 'parsed', 'active',
              NULL, NULL, ?, ?, '{"metrics":{"reward":1,"latency_ms":120}}')
            """,
            (validation_id, project_id, f"alab/source/{source_id}", _now(), _now()),
        )
        conn.execute(
            """
            INSERT INTO experiments(exp_id, project_id, source_id, bound_config_version,
              bound_validation_id, baseline_commit, branch_name, worktree_path, worktree_path_hash,
              worktree_state, status, pre_archive_status, metadata_json, policy_json, latest_run_id,
              latest_commit, final_run_id, final_commit, final_run_removed_at, final_run_removed_by,
              final_run_removed_audit_id, created_at, updated_at, closed_at, archived_at)
            VALUES (?, ?, ?, 1, ?, 'abc123', 'alab/exp/dashboard', NULL, NULL, 'active',
              'open', NULL, ?, ?,
              ?, 'abc123', ?, 'abc123', NULL, NULL, NULL, ?, ?, NULL, NULL)
            """,
            (
                exp_id,
                project_id,
                source_id,
                validation_id,
                json.dumps({"schema_version": 1, "name": "dash-exp", "name_slug": "dash-exp", "goal": "inspect"}),
                json.dumps(
                    {
                        "schema_version": 1,
                        "mutable": {"include": ["**"], "exclude": []},
                        "visibility_upper_bound": {"schema_version": 1, "scope": "same_project", "experiment_ids": []},
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                run_id,
                run_id,
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status,
              exit_code, reward_value, reward_parse_status, archive_status, archived_at,
              unarchived_at, started_at, ended_at, rolled_back_auto_commit, record_json)
            VALUES (?, ?, ?, 'abc123', 1, 'passed', 0, 1.0, 'parsed', 'active',
              NULL, NULL, ?, ?, NULL, '{"metrics":{"reward":1,"latency_ms":120,"coverage":0.95},"warning_codes":[]}')
            """,
            (run_id, exp_id, project_id, _now(), _now()),
        )
        conn.execute(
            """
            INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream,
              size_bytes, stored_bytes, content_hash, truncated, hidden, archive_status, file_path,
              preview_text, archived_at, unarchived_at, created_at)
            VALUES (?, ?, ?, ?, NULL, 'hidden_stdout', 22, 22, 'sha256:hidden', 0, 1,
              'active', ?, 'hidden diagnostic log', NULL, NULL, ?)
            """,
            (log_id, project_id, exp_id, run_id, log_rel, _now()),
        )
        conn.execute(
            """
            INSERT INTO artifacts(artifact_id, project_id, exp_id, run_id, validation_id, root,
              relative_path, size_bytes, content_hash, status, archive_status, blob_path,
              capture_error, archived_at, unarchived_at, created_at)
            VALUES (?, ?, ?, ?, NULL, 'workspace', 'report.txt', 22, 'sha256:artifact',
              'captured', 'active', ?, NULL, NULL, NULL, ?)
            """,
            (artifact_id, project_id, exp_id, run_id, artifact_rel, _now()),
        )
        conn.execute(
            """
            INSERT INTO audit_events(audit_id, project_id, exp_id, actor_credential_id, actor_type,
              action, object_type, object_id, cascade, reason, deleted_ids_json, metadata_json, created_at)
            VALUES (?, ?, ?, NULL, 'system', 'add', 'project', ?, 0, NULL,
              '{"schema_version":1,"counts":{},"ids":{}}', '{"schema_version":1}', ?)
            """,
            (audit_id, project_id, exp_id, project_id, _now()),
        )
    return {
        "project_id": project_id,
        "exp_id": exp_id,
        "run_id": run_id,
        "log_id": log_id,
        "artifact_id": artifact_id,
    }


def test_dashboard_command_is_root_only_and_validates_options(tmp_path: Path, capsys) -> None:
    home, root_key = _init_home(tmp_path, capsys)

    assert cli.run(["--home", str(home.path), "dashboard", "--no-open"]) == 4
    assert "COMMAND_UNAVAILABLE" in capsys.readouterr().err

    assert cli.run(["--home", str(home.path), "--key", root_key, "dashboard", "--port", "65536", "--no-open"]) == 2
    assert "--port must be between 0 and 65535" in capsys.readouterr().err

    assert cli.run(["--home", str(home.path), "--key", root_key, "dashboard", "--refresh-seconds", "3601", "--no-open"]) == 2
    assert "--refresh-seconds must be between 0 and 3600" in capsys.readouterr().err

    ids = _seed_dashboard_data(home)
    with sqlite3.connect(home.db_path) as conn:
        _admin_id, admin_key = create_credential(conn, credential_type="admin", project_id=ids["project_id"])
    assert cli.run(["--home", str(home.path), "--key", admin_key, "dashboard", "--no-open"]) == 4
    assert "COMMAND_UNAVAILABLE" in capsys.readouterr().err

    result = cmd_dashboard(
        ["--port", "0", "--refresh-seconds", "0", "--no-open"],
        Request(globals=GlobalOptions(home=home, key=root_key, key_source="explicit"), context=None),
    )
    try:
        fields = dict(result.blocks[0].fields)
        assert result.blocks[0].object_type == "dashboard"
        assert fields["host"] == "127.0.0.1"
        assert fields["refresh seconds"] == 0
        assert fields["opened"] is False
        assert "#token=" in fields["url"]
    finally:
        assert result.close is not None
        result.close()


def test_dashboard_http_api_is_token_guarded_read_only_and_serves_content(tmp_path: Path, capsys) -> None:
    home, root_key = _init_home(tmp_path, capsys)
    ids = _seed_dashboard_data(home)
    result = cmd_dashboard(
        ["--port", "0", "--refresh-seconds", "0", "--no-open"],
        Request(globals=GlobalOptions(home=home, key=root_key, key_source="explicit"), context=None),
    )
    server = result.close.__self__ if result.close is not None else None
    assert server is not None
    thread = threading.Thread(target=server.httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.port}"
    try:
        with _urlopen(base_url + "/") as response:
            assert response.status == 200
            assert "Content-Security-Policy" in response.headers

        try:
            _urlopen(base_url + "/api/summary")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("missing dashboard token should fail")

        request = urllib.request.Request(
            base_url + "/api/summary",
            headers={DASHBOARD_TOKEN_HEADER: "wrong-token"},
        )
        try:
            _urlopen(request)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("wrong dashboard token should fail")

        request = urllib.request.Request(
            base_url + "/api/summary",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        with _urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["counts"]["feedback"] == 1
            assert payload["counts"]["runs"]["passed"] == 1

        paged_endpoints = {
            "/api/projects?limit=1": "projects",
            "/api/experiments?limit=1": "experiments",
            "/api/runs?limit=1": "runs",
            "/api/logs?limit=1": "logs",
            "/api/artifacts?limit=1": "artifacts",
            "/api/audit?limit=1": "audit",
            "/api/feedback?limit=1&query=dashboard": "feedback",
        }
        for endpoint, key in paged_endpoints.items():
            request = urllib.request.Request(
                base_url + endpoint,
                headers={DASHBOARD_TOKEN_HEADER: server.api_token},
            )
            with _urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
                assert payload["page"]["limit"] == 1
                assert payload["page"]["offset"] == 0
                assert payload["page"]["total"] >= 1
                assert len(payload[key]) == 1

        request = urllib.request.Request(
            base_url + f"/api/projects/{ids['project_id']}",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        with _urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["pages"]["experiments"]["limit"] == 100
            assert payload["pages"]["logs"]["total"] == 1

        request = urllib.request.Request(
            base_url + f"/api/runs/{ids['run_id']}",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        with _urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["pages"]["logs"]["limit"] == 100
            assert payload["pages"]["artifacts"]["total"] == 1

        request = urllib.request.Request(
            base_url + "/api/logs?limit=0",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        try:
            _urlopen(request)
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 400
            assert payload["error"] == "CONFIG_INVALID"
        else:
            raise AssertionError("invalid dashboard list pagination should fail")

        request = urllib.request.Request(
            base_url + f"/api/logs/{ids['log_id']}/content",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        with _urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["log"]["hidden"] is True
            assert "hidden diagnostic log" in payload["content"]

        request = urllib.request.Request(
            base_url + f"/api/logs/{ids['log_id']}/content?offset=7&limit=10",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        with _urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["content"] == "diagnostic"
            assert payload["next_offset"] == 17

        request = urllib.request.Request(
            base_url + f"/api/artifacts/{ids['artifact_id']}/preview",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        with _urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["preview"]["kind"] == "text"
            assert "artifact preview text" in payload["preview"]["content"]

        with sqlite3.connect(home.db_path) as conn:
            conn.execute("UPDATE artifacts SET blob_path = '../../outside.txt' WHERE artifact_id = ?", (ids["artifact_id"],))
        request = urllib.request.Request(
            base_url + f"/api/artifacts/{ids['artifact_id']}/preview",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        try:
            _urlopen(request)
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 500
            assert payload["error"] == "STORAGE_ERROR"
            assert "escapes project artifact store" in payload["reason"]
        else:
            raise AssertionError("artifact path traversal should fail")

        request = urllib.request.Request(
            base_url + "/api/summary",
            data=b"{}",
            method="POST",
            headers={DASHBOARD_TOKEN_HEADER: server.api_token},
        )
        try:
            _urlopen(request)
        except urllib.error.HTTPError as exc:
            assert exc.code == 405
        else:
            raise AssertionError("mutating method should fail")
    finally:
        server.httpd.shutdown()
        server.close()
        thread.join(timeout=5)


def test_dashboard_read_models_redact_raw_secrets(tmp_path: Path, capsys) -> None:
    home, _root_key = _init_home(tmp_path, capsys)
    ids = _seed_dashboard_data(home)
    detail = read_project_detail(home, ids["project_id"])
    serialized = json.dumps(detail, sort_keys=True)

    assert "RAW_SECRET_SHOULD_NOT_LEAK" not in serialized
    assert "hmac-sha256:dashboard" in serialized
    secret_env = detail["configs"][0]["config"]["secret_env"]
    assert secret_env == {"API_TOKEN": {"fingerprint": "hmac-sha256:dashboard"}}
    assert detail["project"]["reference_metrics"] == [
        {
            "name": "latency_ms",
            "label": "Latency",
            "direction": "minimize",
            "unit": "ms",
        },
        {"name": "coverage", "label": "Coverage", "direction": "maximize", "unit": None},
    ]
    assert detail["runs"][0]["metrics"]["latency_ms"] == 120
    assert detail["runs"][0]["metrics"]["coverage"] == 0.95


def test_report_command_exports_project_and_experiment_markdown(tmp_path: Path, capsys, monkeypatch) -> None:
    home, root_key = _init_home(tmp_path, capsys)
    ids = _seed_dashboard_data(home)
    incompatible_run_id = "run-dashboard-BBBBBBBBBBBBBBBBBBBBBB"
    project_report = tmp_path / "project-report.md"
    exp_report = tmp_path / "experiment-report.md"
    token_worktree = tmp_path / "token-worktree"
    token_worktree.mkdir()
    token_path_hash = path_hash(token_worktree)
    with sqlite3.connect(home.db_path) as conn:
        config_v1 = json.loads(
            conn.execute(
                "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = 1",
                (ids["project_id"],),
            ).fetchone()[0]
        )
        config_v2 = {**config_v1, "reward": {**config_v1["reward"], "primary_metric": "other_reward"}}
        conn.execute(
            """
            INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
              baseline_required, validation_status, inherited_from_validation_id, created_at,
              created_by_credential_id)
            VALUES (?, 2, ?, 'sha256:dashboard-v2', 0, 'failed', NULL, ?, NULL)
            """,
            (ids["project_id"], json.dumps(config_v2, sort_keys=True, separators=(",", ":")), _now()),
        )
        conn.execute(
            "UPDATE projects SET latest_attempted_config_version = 2 WHERE project_id = ?",
            (ids["project_id"],),
        )
        conn.execute(
            """
            INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status,
              exit_code, reward_value, reward_parse_status, archive_status, archived_at,
              unarchived_at, started_at, ended_at, rolled_back_auto_commit, record_json)
            VALUES (?, ?, ?, 'def456', 2, 'passed', 0, 999.0, 'parsed', 'active',
              NULL, NULL, ?, ?, NULL, '{"metrics":{"reward":999},"warning_codes":[]}')
            """,
            (incompatible_run_id, ids["exp_id"], ids["project_id"], _now(), _now()),
        )
        token_id, raw_token = create_credential(
            conn,
            credential_type="token",
            project_id=ids["project_id"],
            exp_id=ids["exp_id"],
            token_mode="worktree",
            registered_path_hash=token_path_hash,
        )
        home_id = conn.execute("SELECT home_id FROM homes LIMIT 1").fetchone()[0]
        conn.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
              exp_id, token_id, status, removed_at, removed_by_credential_id, created_at, updated_at)
            VALUES (?, ?, ?, 'experiment', ?, ?, ?, ?, 'active', NULL, NULL, ?, ?)
            """,
            (new_id("path", "experiment"), token_path_hash, str(token_worktree), home_id, ids["project_id"], ids["exp_id"], token_id, _now(), _now()),
        )
    write_marker(
        token_worktree,
        {
            "marker_version": 1,
            "home_id": home_id,
            "context_type": "experiment",
            "project_id": ids["project_id"],
            "exp_id": ids["exp_id"],
            "token_id": token_id,
            "created_at": _now(),
        },
    )
    write_token(token_worktree, raw_token)

    assert cli.run(["--home", str(home.path), "--key", root_key, "report", "--project", ids["project_id"], "--out", str(project_report)]) == 0
    fields = _field_map(capsys.readouterr().out)
    assert fields["scope"] == "project"
    assert fields["project id"] == ids["project_id"]
    assert fields["out"] == str(project_report)
    project_text = project_report.read_text(encoding="utf-8")
    assert "# ALab Project Report" in project_text
    assert ids["project_id"] in project_text
    assert f"| best run | {ids['run_id']} |" in project_text
    assert f"| best run | {incompatible_run_id} |" not in project_text
    assert "RAW_SECRET_SHOULD_NOT_LEAK" not in project_text
    assert "hidden diagnostic log" not in project_text

    monkeypatch.chdir(token_worktree)
    assert (
        cli.run(
            [
                "--home",
                str(home.path),
                "report",
                "--exp",
                ids["exp_id"],
                "--out",
                str(exp_report),
            ]
        )
        == 0
    )
    fields = _field_map(capsys.readouterr().out)
    assert fields["scope"] == "experiment"
    assert fields["exp id"] == ids["exp_id"]
    exp_text = exp_report.read_text(encoding="utf-8")
    assert "# ALab Experiment Report" in exp_text
    assert ids["run_id"] in exp_text
    assert f"| best run | {ids['run_id']} |" in exp_text
    assert f"| best run | {incompatible_run_id} |" not in exp_text
    assert ids["log_id"] not in exp_text
    assert "hidden diagnostic log" not in exp_text

    assert cli.run(["--home", str(home.path), "--key", root_key, "report", "--project", ids["project_id"], "--out", str(project_report)]) == 2
    assert "OUTPUT_EXISTS" in capsys.readouterr().err


def test_dashboard_static_frontend_uses_external_scripts_and_translation_pairs() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "alab" / "dashboard_static"
    index = (root / "index.html").read_text(encoding="utf-8")
    app = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    assert "<script>" not in index
    assert "onClick" not in index and "onclick" not in index
    assert "style=" not in app
    assert "Local Viewer" in index
    assert "Root Dashboard" not in index
    assert "Root 面板" not in app
    assert "last-refresh" in index
    assert "clear-search" in index
    assert 'id="detail-backdrop"' in index
    assert 'aria-hidden="true"' in index
    assert "global.searchPlaceholder" in app
    assert "global.clearSearch" in app
    assert "renderFreshness" in app
    assert "renderSearchControl" in app
    assert 'L("No records are available for this section.", "此区域暂无可显示记录。")' in app
    assert "options.unfiltered" in app
    assert "resourceCardsHtml(rows, kind, options = {})" in app
    assert 'resourceCardsHtml(rows, "logs", { total: allRows.length })' in app
    assert 'resourceCardsHtml(rows, "artifacts", { total: allRows.length })' in app
    assert "state.pages.projects" in app
    assert 'L("loaded", "已加载")' in app
    assert "page: detail.pages && detail.pages.logs" in app
    assert "page: detail.pages && detail.pages.runs" in app
    assert "page: state.assetScope && state.assetScope.pages && state.assetScope.pages.artifacts" in app
    assert 'api(`/api/logs?limit=500${projectParam}`)' in app
    assert 'api(`/api/artifacts?limit=500${projectParam}`)' in app
    assert "Promise.all(state.projects.map((project) => fetchProjectDetail(project.project_id)))" not in app
    assert "formatCompactDate" in app
    assert "month: \"numeric\"" in app
    assert "hour12: false" in app
    assert "detailRerender" in app
    assert "detailSuppressFocus" in app
    assert "projectDetailTab" in app
    assert "rerenderOpenDetailPanel" in app
    assert "Refresh detail" in app
    assert "refresh-detail" in app
    assert "showRefreshButton" in app
    assert "options.refreshable" in app
    assert "refreshable: true" in app
    assert "resolveObjectTitle" in app
    assert 'typeof title === "function" ? title() : title' in app
    assert 'showObject(() => L("Audit", "审计")' in app
    assert "detail-actions" in app
    assert "rerenderOpenDetailPanel({ preserveFocus: true })" in app
    assert "await rerenderOpenDetailPanel();" in app
    assert "showProject(projectId, options = {})" in app
    assert 'rerender: () => showProject(projectId, { tab: state.projectDetailTab || "overview" })' in app
    assert "document.documentElement.lang" in app
    assert "filterMeta" in app
    assert 'const parts = [`${L("Showing", "显示")} ${shown}/${total}`];' in app
    assert "const visibleOptions = options.filter" in app
    assert 'option.value === "all"' in app
    assert "Number(option.count || 0) > 0" in app
    assert 'disabled aria-disabled="true"' not in app
    assert ".quick-filters button:disabled" not in styles
    assert "-webkit-overflow-scrolling: touch;" in styles
    assert "flex-wrap: nowrap;" in styles
    assert "grid-template-columns: auto minmax(160px, 220px);" in styles
    assert ".sort-shell select" in styles
    assert "shortText" in app
    assert "factValue" in app
    assert "function renderListChrome" in app
    assert "if (!allRows.length)" in app
    assert 'controlsNode.innerHTML = "";' in app
    assert 'metaNode.innerHTML = "";' in app
    assert app.count("renderListChrome({") >= 8
    assert "openCardLabel" in app
    assert "cardLabelAttrs" in app
    assert 'aria-label="${escapeHtml(text)}"' in app
    assert 'title="${escapeHtml(text)}"' in app
    assert 'class="metric-value" title="${escapeHtml(value)}"' in app
    assert "source detail" in app
    assert "validation detail" in app
    assert "annotation detail" in app
    assert "capability detail" in app
    assert "cache detail" in app
    assert "attention detail" in app
    assert "highlight detail" in app
    assert "home-status-text" in app
    assert "home-status-text" in styles
    assert "home-path-group" in app
    assert ".home-path-group" in styles
    assert "display: inline-flex;" in styles
    assert "min-inline-size: fit-content;" in styles
    assert "word-break: keep-all;" in styles
    assert "text-wrap: nowrap;" in styles
    assert "writing-mode: horizontal-tb;" in styles
    assert ".sidebar" in styles
    assert "height: 100vh;" in styles
    assert "overflow-y: auto;" in styles
    assert "align-self: stretch;" in styles
    assert "height: auto;" in styles
    assert ".detail-actions" in styles
    assert ".detail-refresh-button svg" in styles
    assert "grid-template-columns: max-content minmax(0, 1fr);" in styles
    assert "@media (max-width: 420px)" in styles
    assert ".home-path-group {\n    grid-template-columns: 1fr;" in styles
    assert "scroll-snap-type: x proximity;" in styles
    assert "mask-image: linear-gradient(90deg" in styles
    assert "overscroll-behavior-x: contain;" in styles
    assert "scroll-snap-align: start;" in styles
    assert ".brand-subtitle {\n    display: none;" in styles
    assert ".content > .grid.cards:not(.detail-kpis) .metric-value" in styles
    assert "overflow-x: auto;" in styles
    assert "flex: 0 0 auto;" in styles
    assert "--topbar-sticky-top: 0px;" in styles
    assert "top: var(--topbar-sticky-top);" in styles
    assert "--topbar-sticky-top: 62px;" in styles
    assert "#view-subtitle {\n    display: none;" in styles
    assert "grid-template-columns: minmax(0, 1fr) auto auto auto auto;" in styles
    assert "justify-content: stretch;" in styles
    assert ".topbar-actions input" in styles
    assert "backdrop-filter: blur(10px);" in styles
    assert "text-overflow: ellipsis;" in styles
    assert "sizeListHtml" in app
    assert "closeDetailPanel" in app
    assert 'aria-label="${escapeHtml(closeLabel)}"' in app
    assert "project-card-meta" in app
    assert "searchFromLocation" in app
    assert "updateSearchQuery" in app
    assert "window.location.pathname}${window.location.search" in app
    assert "alab-dashboard-asset-kind" in app
    assert 'document.getElementById("asset-project-select").onchange' in app
    assert 'renderAssets(selectedKind)' in app
    assert "artifactKind" in app
    assert "artifactCardSummary" in app
    assert 'artifact.capture_error || artifactCardSummary(artifact)' in app
    assert "assets-log-streams" in app
    assert "assets-artifact-status" in app
    assert "assets-artifact-kinds" in app
    assert "assets-insights" in app
    assert ".assets-insights .panel-body" in styles
    assert "max-height: min(170px, 22vh);" in styles
    assert "resourceCardsHtml" in app
    assert "wireResourceCards" in app
    assert "asset-card-grid" in app
    assert "bounded-list" in app
    assert "bounded-list" in styles
    assert app.count("bounded-list") >= 16
    assert 'id="projects-cards" class="project-card-grid bounded-list"' in app
    assert 'id="audit-feed" class="audit-feed bounded-list"' in app
    assert 'id="system-cache-cards" class="record-card-grid bounded-list"' in app
    assert ".record-card-grid" in styles
    assert "data-artifact-id" in app
    assert "data-log-id" in app
    assert "auditCardsHtml" in app
    assert "wireAuditCards" in app
    assert "renderAuditActivityChart" in app
    assert "audit-activity-chart" in app
    assert "audit-insights" in app
    assert "audit-mix-grid" in app
    assert ".audit-insights .panel-body" in styles
    assert ".audit-mix-grid" in styles
    assert "Audit activity" in app
    assert "Object mix" in app
    assert "Project coverage" in app
    assert "audit-objects" in app
    assert "audit-projects" in app
    assert "recentActivityNode.innerHTML = auditCardsHtml" in app
    assert 'id="recent-activity" class="audit-feed compact-feed"' in app
    assert "annotationCardsHtml" in app
    assert "wireAnnotationCards" in app
    assert "sourceCardsHtml" in app
    assert "validationCardsHtml" in app
    assert "wireRecordCards" in app
    assert "systemCardsHtml" in app
    assert "wireSystemCards" in app
    assert "jsonShape" in app
    assert "jsonDetails" in app
    assert "json-empty" in app
    assert 'L("No record", "没有记录")' in app
    assert ".json-empty" in styles
    assert "objectDetailHtml" in app
    assert "panel-actions" in app
    assert "const actionsHtml = actions ?" in app
    assert ".panel-actions" in styles
    assert "objectKeyFields" in app
    assert "objectDisplayValue" in app
    assert "Raw record" in app
    assert "Key fields" in app
    assert "items" in app
    assert "keys" in app
    assert "system-lock-cards" in app
    assert "system-capability-cards" in app
    assert "system-catalog-cards" in app
    assert "system-cache-cards" in app
    assert "Cache footprint" in app
    assert "system-insights" in app
    assert 'metric(L("Latest", "最新"), formatCompactDate(latestValue(rows, (row) => row.created_at))' in app
    assert 'metric(L("Latest", "最新"), formatCompactDate(latestValue(filtered, (row) => row.metadata && row.metadata.created_at))' in app
    assert ".system-insights .panel-body" in styles
    assert "system-cache-kind-size" in app
    assert "system-cache-project-size" in app
    assert "project-annotation-cards" in app
    assert "project-audit-cards" in app
    assert "project-source-cards" in app
    assert "project-validation-cards" in app
    assert "project-log-cards" in app
    assert "project-artifact-cards" in app
    assert "exp-log-cards" in app
    assert "exp-artifact-cards" in app
    assert "run-log-cards" in app
    assert "run-artifact-cards" in app
    assert "vendor/chart.umd.js" in index
    assert "destroyChartsIn" in app
    assert "state.charts.delete(canvas.id)" in app
    assert "destroyChartsIn(content)" in app
    for key in ["overview.subtitle", "projects.subtitle", "experiments.subtitle", "runs.subtitle"]:
        assert f'"{key}"' in app
    assert "X-ALab-Dashboard-Token" in app
    assert "state.refreshSeconds > 0" in app
    assert "escapeHtml(error.message)" in app
    assert "project-reward-chart" in app
    assert "overview-run-activity-chart" in app
    assert "project-chart-box" in app
    assert "project-overview-grid" in app
    assert "project-overview-side" in app
    assert ".project-overview-grid" in styles
    assert ".project-overview-side .panel-body" in styles
    assert "max-height: min(260px, 30vh);" in styles
    assert app.index('${panel(L("Run reward trend", "运行奖励趋势")') < app.index(
        '${panel(L("Project highlights", "项目要点")'
    )
    assert "best-so-far high" in app
    assert "bestSoFar" in app
    assert "data: data.bestSoFar" in app
    assert 'pointRadius: data.bestPoints.map((value) => value === null ? 0 : 5)' in app
    assert "运行奖励" in app
    assert "累计最高最佳" in app
    assert 'label: L("experiments", "实验")' in app
    assert '`${L("status", "状态")}: ${statusLabel(run.status || "none")}`' in app
    assert 'label: "experiments"' not in app
    assert "Project statistics" in app
    assert 'data-tab="overview"' in app
    assert "project-stats-grid" in styles
    assert "repeat(auto-fit, minmax(min(150px, 100%), 1fr))" in styles
    assert "repeat(auto-fit, minmax(min(128px, 100%), 1fr))" in styles
    assert ".project-stats-grid .metric-note {\n  line-height: 1.25;\n  overflow-wrap: anywhere;\n  white-space: normal;" in styles
    assert ".project-detail-summary > .badge" in styles
    assert "grid-template-columns: minmax(0, 1fr) max-content;" in styles
    assert "detail-kpis" in app
    assert ".detail-kpis" in styles
    assert "min-height: 116px;" in styles
    assert "padding-bottom: 12px;" in styles
    assert ".detail-kpis .card {\n  flex: 0 0 clamp(128px, 21vw, 178px);\n  min-height: 96px;" in styles
    assert ".content > .grid.cards:not(.detail-kpis)" in styles
    assert ".content > .grid.cards:not(.detail-kpis) {\n    display: grid;\n    grid-template-columns: repeat(2, minmax(0, 1fr));" in styles
    assert ".content > .grid.cards:not(.detail-kpis) {\n    grid-template-columns: 1fr;" in styles
    assert ".project-summary-grid,\n  .project-signals {\n    display: grid;\n    grid-template-columns: 1fr;" in styles
    assert "@media (max-width: 420px)" in styles
    assert "run order" in app
    assert "运行序号" in app
    assert "statusLabel" in app
    assert "statusCountText" in app
    assert "quickFilters" in app
    assert "wireQuickFilters" in app
    assert "sortControl" in app
    assert "wireSortControl" in app
    assert "sortProjects" in app
    assert "sortExperiments" in app
    assert "sortRuns" in app
    assert "filterLogs" in app
    assert "sortLogs" in app
    assert "filterArtifacts" in app
    assert "sortArtifacts" in app
    assert "filterAuditRows" in app
    assert "sortAuditRows" in app
    assert "filterFeedbackRows" in app
    assert "sortFeedbackRows" in app
    assert "feedbackBodyWords" in app
    assert "feedback-recency" in app
    assert "feedback-card-facts" in styles
    assert "Most detailed" in app
    assert "filterCapabilities" in app
    assert "sortCapabilities" in app
    assert "filterCatalogs" in app
    assert "sortCatalogs" in app
    assert "filterCacheRows" in app
    assert "sortCacheRows" in app
    assert "alab-dashboard-sort-projects" in app
    assert "alab-dashboard-sort-asset_logs" in app
    assert "alab-dashboard-sort-audit" in app
    assert "alab-dashboard-sort-feedback" in app
    assert "alab-dashboard-asset-project" in app
    assert "alab-dashboard-sort-project_runs" in app
    assert "alab-dashboard-sort-project_artifacts" in app
    assert "alab-dashboard-sort-experiment_runs" in app
    assert "alab-dashboard-sort-experiment_artifacts" in app
    assert "alab-dashboard-sort-run_logs" in app
    assert "alab-dashboard-sort-run_artifacts" in app
    assert "alab-dashboard-sort-system_capabilities" in app
    assert "alab-dashboard-sort-system_catalogs" in app
    assert "alab-dashboard-sort-system_cache" in app
    assert "filterProjects" in app
    assert "filterExperiments" in app
    assert "filterRuns" in app
    assert "alab-dashboard-filter-projects" in app
    assert "alab-dashboard-filter-asset_artifacts" in app
    assert "alab-dashboard-filter-audit" in app
    assert "alab-dashboard-filter-feedback" in app
    assert "alab-dashboard-filter-project_experiments" in app
    assert "alab-dashboard-filter-project_logs" in app
    assert "alab-dashboard-filter-experiment_runs" in app
    assert "alab-dashboard-filter-experiment_logs" in app
    assert "alab-dashboard-filter-run_logs" in app
    assert "alab-dashboard-filter-run_artifacts" in app
    assert "alab-dashboard-filter-system_capabilities" in app
    assert "alab-dashboard-filter-system_catalogs" in app
    assert "alab-dashboard-filter-system_cache" in app
    assert "projects-controls" in app
    assert "experiments-controls" in app
    assert "runs-controls" in app
    assert "assets-controls" in app
    assert "assetProjectSelector" in app
    assert "project-summary-grid" in app
    assert ".project-summary-grid" in styles
    assert ".project-summary-grid > .panel,\n  .project-signals > .panel {\n    min-width: 0;" in styles
    assert "scroll-snap-align: none;" in styles
    assert "ensureAssetScope" in app
    assert "asset-project-select" in app
    assert "All projects" in app
    assert "scope-note" in styles
    assert "audit-controls" in app
    assert "feedback-controls" in app
    assert "system-capability-controls" in app
    assert "system-catalog-controls" in app
    assert "system-cache-controls" in app
    assert "systemMetadataHtml" in app
    assert "Home metadata" in app
    assert "project-exp-controls" in app
    assert "project-run-controls" in app
    assert "project-log-controls" in app
    assert "project-artifact-controls" in app
    assert "exp-run-controls" in app
    assert "exp-log-controls" in app
    assert "exp-artifact-controls" in app
    assert "run-log-controls" in app
    assert "run-artifact-controls" in app
    assert "有效" in app
    assert "projects-cards" in app
    assert "project-card-grid" in app
    assert "overview-primary-grid" in app
    assert "overview-secondary-grid" in app
    assert ".overview-primary-grid .attention-list" in styles
    assert "max-height: 224px;" in styles
    assert "max-height: min(300px, 40vh);" in styles
    assert ".overview-primary-grid > .panel:nth-child(2)" in styles
    assert "order: -1;" in styles
    assert "@media (max-width: 760px)" in styles
    assert "grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr));" in styles
    assert "projectSignalListHtml" in app
    assert "project-signal-attention" in app
    assert "project-signal-activity" in app
    assert "project-signal-output" in app
    assert "grid-template-columns: minmax(0, 1.2fr) minmax(56px, 2fr) max-content;" in styles
    assert ".count-row span {\n  min-width: 0;\n  overflow-wrap: anywhere;\n  white-space: normal;" in styles
    assert ".count-row progress" in styles
    assert "grid-template-columns: minmax(0, 0.8fr) minmax(56px, 2fr) max-content;" in styles
    assert ".status-row progress" in styles
    assert ".reason-row strong {\n  min-width: 0;\n  overflow-wrap: anywhere;\n  white-space: normal;" in styles
    assert "Most active" in app
    assert "Largest output" in app
    assert "signal-list" in styles
    assert ".project-signals .panel-body" in styles
    assert "max-height: min(220px, 26vh);" in styles
    assert "experimentCardsHtml" in app
    assert "wireExperimentCards" in app
    assert "countExperimentTags" in app
    assert "experiments-insights" in app
    assert ".experiments-insights .panel-body" in styles
    assert "max-height: min(240px, 28vh);" in styles
    assert "Worktree and latest run" in app
    assert "Tags and projects" in app
    assert "experiments-worktree-mix" in app
    assert "experiments-latest-run-mix" in app
    assert "experiments-tag-mix" in app
    assert "experiments-project-mix" in app
    assert "experimentTimelineHtml" in app
    assert "Experiment timeline" in app
    assert "experimentHighlightsHtml" in app
    assert "Experiment highlights" in app
    assert "experiment-overview-grid" in app
    assert "experiment-overview-side" in app
    assert ".experiment-overview-grid" in styles
    assert ".experiment-overview-side .panel-body" in styles
    assert "wireExperimentHighlights" in app
    assert "bestRunForRuns" in app
    assert "latest reward" in app
    assert "Reference metric trends" in app
    assert "referenceMetricTrendData" in app
    assert "renderReferenceMetricChart" in app
    assert "project-reference-metric-trends" in app
    assert ".reference-metric-grid" in styles
    assert ".reference-metric-chart-box" in styles
    assert "实验时间线" in app
    assert "project-exp-cards" in app
    assert "row-action" in app
    assert "wide: true" in app
    assert "subtitle:" in app
    assert "Config highlights" in app
    assert "projectHealthHtml" in app
    assert "projectHealthBlock" in app
    assert "health-block" in app
    assert "projectHighlightsHtml" in app
    assert "Project highlights" in app
    assert "wireProjectHighlights" in app
    assert "wireDetailTabs" in app
    assert "alignDetailTabBody" in app
    assert "wireAssetTabs" in app
    assert 'button.setAttribute("tabindex", button.dataset.kind === selectedKind ? "0" : "-1")' in app
    assert "requestAnimationFrame" in app
    assert "ArrowRight" in app
    assert "Home" in app
    assert ".detail-tabs" in styles
    assert "position: sticky" in styles
    assert "--detail-content-pad-y" in styles
    assert "top: calc(-1 * var(--detail-content-pad-y, 14px));" in styles
    assert "margin: -2px calc(-1 * var(--detail-content-pad-x, 16px)) 0;" in styles
    assert "highlight-list" in styles
    assert ".highlight-copy strong" in styles
    assert "failureReasonsForRunsHtml" in app
    assert "Project health" in app
    assert "Project failure reasons" in app
    assert "Run coverage" in app
    assert "Attention queue" in app
    assert "Failure reasons" in app
    assert "Run timeline" in app
    assert "runHighlightsHtml" in app
    assert "Run highlights" in app
    assert "run-overview-grid" in app
    assert "run-overview-side" in app
    assert ".run-overview-grid" in styles
    assert ".run-overview-side .panel-body" in styles
    assert "wireRunHighlights" in app
    assert "data-highlight-log-id" in app
    assert "data-highlight-artifact-id" in app
    assert "logHighlightsHtml" in app
    assert "artifactHighlightsHtml" in app
    assert "wireEvidenceHighlights" in app
    assert "Log evidence" in app
    assert "Artifact evidence" in app
    assert "evidence-highlight-list" in app
    assert ".evidence-highlight-list" in styles
    assert ".log-search-row" in styles
    assert ".log-action-row" in styles
    assert "copy-artifact-preview" in app
    assert "Copy text preview" in app
    assert "Download raw artifact" in app
    assert ".artifact-copy-status:not(:empty)" in styles
    assert app.count('wireEvidenceHighlights(document.getElementById("detail-panel"))') >= 2
    assert "Runner and project mix" in app
    assert "runs-insights" in app
    assert "runs-mix-insights" in app
    assert ".runs-insights .panel-body" in styles
    assert ".runs-mix-insights" in styles
    assert "runs-failure-reasons" in app
    assert "runs-runner-mix" in app
    assert "runs-project-mix" in app
    assert "run-card-grid" in app
    assert "runCardTone" in app
    assert "runTimelineHtml" in app
    assert "runnerCompactSummary" in app
    assert "timelineStep" in app
    assert "runDuration" in app
    assert "Duration" in app
    assert "耗时" in app
    assert "runCardsHtml" in app
    assert "wireRunCards" in app
    assert "project-run-cards" in app
    assert "exp-run-cards" in app
    assert "relatedActions({ project_id: exp.project_id })" in app
    assert "relatedActions({ project_id: run.project_id, exp_id: run.exp_id })" in app
    assert 'record.object_type === "project"' in app
    assert 'record.object_type === "experiment"' in app
    assert 'record.object_type === "run"' in app
    assert app.count('wireRelatedActions(document.getElementById("detail-panel"))') >= 4
    assert "project-run-table" not in app
    assert "exp-run-table" not in app
    assert "project-exp-table" not in app
    assert "project-log-table" not in app
    assert "project-artifact-table" not in app
    assert "exp-log-table" not in app
    assert "exp-artifact-table" not in app
    assert "run-log-table" not in app
    assert "run-art-table" not in app
    assert "project-annotation-table" not in app
    assert "project-audit-table" not in app
    assert "project-source-table" not in app
    assert "project-validation-table" not in app
    assert 'id="system-locks"' not in app
    assert 'id="system-capabilities"' not in app
    assert 'id="system-catalogs"' not in app
    assert 'id="system-cache"' not in app
    assert 'id="recent-activity" class="table-wrap"' not in app
    assert "Risk" in app
    assert "log-search" in app
    assert "load-log-more" in app
    assert "Log record" in app
    assert "Artifact record" in app
    assert "metricSummaryHtml" in app
    assert "metric-list" in app
    assert "jsonPre(run.metrics" not in app
    assert "aria-sort" in app
    assert 'setAttribute("tabindex", "0")' in app
    assert "button:focus-visible" in styles
    assert ".project-card:focus-visible" in styles
    assert ".project-card:focus" in styles
    assert "INTERACTIVE_CARD_SELECTOR" in app
    assert "wireInteractiveFocusState" in app
    assert 'classList.add("is-focused")' in app
    assert 'window.requestAnimationFrame(() => mark(document.activeElement || event.target))' in app
    assert 'document.addEventListener("pointerdown", () => clear())' in app
    assert ".project-card.is-focused" in styles
    assert ".attention-item.is-focused" in styles
    assert "transform: translateY(-1px);" in styles
    assert 'setAttribute("role", "button")' in app
    assert 'setAttribute("aria-current", "page")' in app
    assert 'setAttribute("role", "dialog")' in app
    assert 'setAttribute("aria-modal", "true")' in app
    assert 'setAttribute("aria-labelledby", "detail-title")' in app
    assert 'setAttribute("aria-describedby", "detail-subtitle")' in app
    assert 'removeAttribute("role")' in app
    assert 'removeAttribute("aria-labelledby")' in app
    assert 'removeAttribute("aria-modal")' in app
    assert "const kicker = options.kicker ||" in app
    assert "detail-kicker" in app
    assert 'id="detail-title"' in app
    assert 'id="detail-subtitle"' in app
    assert "detail-title-row" in app
    assert ".detail-kicker" in styles
    assert ".detail-title-row" in styles
    assert ".detail-subtitle" in styles
    assert ".detail-subtitle {\n  display: -webkit-box;" in styles
    assert "-webkit-line-clamp: 2;" in styles
    assert 'document.getElementById("detail-backdrop")' in app
    assert 'detailBackdrop.addEventListener("click"' in app
    assert 'document.body.classList.add("detail-open")' in app
    assert 'document.body.classList.remove("detail-open")' in app
    assert "panelEl.replaceChildren()" in app
    assert "detailScrollLockY" in app
    assert 'document.body.style.top = `-${state.detailScrollLockY}px`' in app
    assert "window.scrollTo(0, state.detailScrollLockY || 0)" in app
    assert "body.detail-open" in styles
    assert "position: fixed;" in styles
    assert ".detail-backdrop" in styles
    assert ".detail-backdrop[hidden]" in styles
    assert "const subtitle = options.subtitle ||" in app
    assert ".detail-subtitle" in styles
    assert "subtitle: projectSummary" in app
    assert "subtitle: `${projectName(log.project_id)}" in app
    assert 'setAttribute("aria-pressed", String(state.paused))' in app
    assert "detailFocusableElements" in app
    assert "trapDetailPanelFocus" in app
    assert 'event.key === "Tab"' in app
    assert "panelEl.contains(document.activeElement)" in app
    assert 'role="tablist"' in app
    assert 'role="tab"' in app
    assert "detailReturnFocus" in app
    assert "focus({ preventScroll: true })" in app
    assert 'closeButton.addEventListener("keydown"' in app
    assert 'canvas.setAttribute("role", "img")' in app
    assert 'canvas.setAttribute("aria-label"' in app
    assert "Run reward trend. The main line shows every run reward and the red line carries the best-so-far value forward" in app
    assert "按日期和状态统计的运行活动" in app
    assert "按状态统计的实验数量" in app
    assert "rewardTrendSummaryHtml" in app
    assert "trendSummaryItem" in app
    assert "project-reward-summary" in app
    assert "experiment-reward-summary" in app
    assert "new best points" in app
    assert ".trend-summary" in styles
    assert ".trend-summary-item" in styles
    assert "log-prev-match" in app
    assert "log-next-match" in app
    assert 'aria-label="${escapeHtml(L("Find in log", "在日志中查找"))}"' in app
    assert "log-copy-status" in app
    assert "copied loaded content" in app
    assert "copyTextToClipboard" in app
    assert 'document.execCommand("copy")' in app
    assert ".clipboard-buffer" in styles
    assert "Copy loaded log content" in app
    assert "active-log-match" in app
    assert "scrollIntoView" in app
    assert "1} / ${matches}" in app
    assert "const canStep = matches > 1" in app
    assert ".log-match-button" in styles
    assert ".log-state-pill" in styles
    assert ".log-copy-status:not(:empty)" in styles
    assert "mark.active-log-match" in styles
    assert "Compare diff" not in app
    assert "selectedExperiments" not in app
    assert "flex: 0 0 auto" in styles
    assert "grid-template-columns: repeat(auto-fit, minmax(320px, 1fr))" in styles
    assert ".scroll-table" in styles
    assert ".row-action" in styles
    assert ".refresh-meta" in styles
    assert ".filter-meta" in styles
    assert ".quick-filters" in styles
    assert ".quick-filters button.active" in styles
    assert "data-reset-filter" in app
    assert "Reset filter" in app
    assert "alab-dashboard-filter-${targetView}" in app
    assert ".list-tools" in styles
    assert ".reset-filter-control" in styles
    assert ".signal-main strong" in styles
    assert ".list-controls" in styles
    assert ".sort-shell" in styles
    assert ".entity-summary > div:first-child" in styles
    assert ".metric-list" in styles
    assert ".reason-row strong {\n  min-width: 0;\n  overflow-wrap: anywhere;\n  white-space: normal;\n  line-height: 1.25;" in styles
    assert ".project-health-grid" in styles
    assert ".health-block" in styles
    assert "project-chart-box" in styles
    assert "height: clamp(240px, 30vh, 340px);" in styles
    assert ".detail-tabs {\n    flex-wrap: nowrap;" in styles
    assert "#project-reward-summary .trend-summary" in styles
    assert "#project-reward-summary .trend-summary-item" in styles
    assert ".run-card-grid" in styles
    assert ".run-card.has-risk" in styles
    assert "grid-template-columns: repeat(auto-fit, minmax(76px, 1fr))" in styles
    assert ".timeline-strip" in styles
    assert ".timeline-step.has-risk" in styles
    assert ".asset-card-grid" in styles
    assert ".asset-card.has-warning" in styles
    assert ".asset-card-facts b" in styles
    assert (
        "color: var(--text);\n"
        "  font-size: 12px;\n"
        "  line-height: 1.25;\n"
        "  min-height: 17px;"
        in styles
    )
    assert ".resource-insights" in styles
    assert ".annotation-card" in styles
    assert ".audit-feed.compact-feed" in styles
    assert ".record-card" in styles
    assert ".record-card-grid" in styles
    assert ".system-card" in styles
    assert ".json-disclosure[open] summary::after" in styles
    assert ".json-disclosure pre" in styles
    assert "flex-wrap: nowrap" in styles
    assert "overflow-wrap: normal" in styles
    assert "overflow-wrap: anywhere" in styles
    assert "compare-bar" not in styles


def test_dashboard_showcase_example_generator_creates_readable_home(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "examples" / "dashboard_showcase" / "scripts" / "create_demo_home.py"
    spec = importlib.util.spec_from_file_location("dashboard_showcase_create_demo_home", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    home = Home(tmp_path / "showcase-home")
    assert module.main(["--home", str(home.path), "--force"]) == 0

    summary = read_summary(home)
    system = read_system(home)
    clinic = read_project_detail(home, "proj-showcase-clinic-ops")

    assert sum(summary["counts"]["projects"].values()) == 4
    assert summary["counts"]["runs"]["passed"] >= 8
    assert summary["counts"]["runs"]["timeout"] == 1
    assert summary["counts"]["logs"]["hidden_stdout"] >= 4
    assert summary["counts"]["artifacts"]["captured"] >= 10
    assert summary["counts"]["feedback"] == 3
    assert summary["counts"]["active_locks"] == 1
    assert len(system["capabilities"]) == 3
    assert len(system["cache_entries"]) == 3
    assert len(clinic["experiments"]) == 2
    assert len(clinic["runs"]) >= 5
