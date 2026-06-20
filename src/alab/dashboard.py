from __future__ import annotations

import base64
import json
import mimetypes
import secrets
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .configs import load_global_config, project_config_json_obj
from .db import all_rows, connect_initialized, one
from .errors import AlabError
from .home import Home
from .rendering import ResultBlock
from .service_args import (
    _parse_int_option,
    flag,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_actor
from .service_models import LongRunningResult, Request

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_TOKEN_HEADER = "X-ALab-Dashboard-Token"
DEFAULT_REFRESH_SECONDS = 15
MAX_CONTENT_CHUNK_BYTES = 1024 * 1024
DEFAULT_CONTENT_CHUNK_BYTES = 64 * 1024
DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 500
MAX_PREVIEW_BYTES = 512 * 1024
STATIC_ROOT = resources.files("alab").joinpath("dashboard_static")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".md": "text/markdown; charset=utf-8",
}


def cmd_dashboard(args: list[str], req: Request) -> LongRunningResult:
    require_known_options(args, ("--port", "--no-open", "--refresh-seconds"))
    require_options_at_most_once(args, ("--port", "--no-open", "--refresh-seconds"))
    require_actor(req, "root")
    require_positional_count(
        args,
        0,
        "dashboard accepts no positional arguments",
        options_with_values=("--port", "--refresh-seconds"),
    )
    port = _parse_int_option(args, "--port")
    if port is None:
        port = 0
    if port < 0 or port > 65535:
        raise AlabError("CONFIG_INVALID", "--port must be between 0 and 65535")
    refresh_seconds = _parse_int_option(args, "--refresh-seconds")
    if refresh_seconds is None:
        refresh_seconds = DEFAULT_REFRESH_SECONDS
    if refresh_seconds < 0 or refresh_seconds > 3600:
        raise AlabError("CONFIG_INVALID", "--refresh-seconds must be between 0 and 3600")
    server = create_dashboard_server(
        home=req.globals.home,
        port=port,
        refresh_seconds=refresh_seconds,
        open_browser=not flag(args, "--no-open"),
    )
    return LongRunningResult(blocks=server.result_blocks(), run=server.serve, close=server.close)


@dataclass
class DashboardServer:
    home: Home
    httpd: ThreadingHTTPServer
    browser_url: str
    api_token: str
    refresh_seconds: int
    open_browser: bool

    @property
    def host(self) -> str:
        return str(self.httpd.server_address[0])

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def result_blocks(self) -> list[ResultBlock]:
        return [
            ResultBlock(
                "dashboard",
                [
                    ("url", self.browser_url),
                    ("host", self.host),
                    ("port", self.port),
                    ("refresh seconds", self.refresh_seconds),
                    ("opened", self.open_browser),
                    ("auth scope", "root"),
                    ("next", "press Ctrl-C to stop the local read-only dashboard"),
                ],
            )
        ]

    def serve(self) -> int:
        try:
            if self.open_browser:
                webbrowser.open(self.browser_url, new=2)
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.httpd.server_close()
        return 0

    def close(self) -> None:
        self.httpd.server_close()


class _DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], *, home: Home, api_token: str, refresh_seconds: int) -> None:
        super().__init__(server_address, handler_class)
        self.home = home
        self.api_token = api_token
        self.refresh_seconds = refresh_seconds


def create_dashboard_server(
    *,
    home: Home,
    port: int,
    refresh_seconds: int,
    open_browser: bool,
) -> DashboardServer:
    token = secrets.token_urlsafe(32)
    try:
        httpd = _DashboardHTTPServer(
            (DASHBOARD_HOST, port),
            _DashboardHandler,
            home=home,
            api_token=token,
            refresh_seconds=refresh_seconds,
        )
    except OSError as exc:
        raise AlabError("RESOURCE_BUSY", f"dashboard port is unavailable: {port}") from exc
    actual_port = int(httpd.server_address[1])
    url = f"http://{DASHBOARD_HOST}:{actual_port}/#token={token}"
    return DashboardServer(
        home=home,
        httpd=httpd,
        browser_url=url,
        api_token=token,
        refresh_seconds=refresh_seconds,
        open_browser=open_browser,
    )


class _DashboardHandler(BaseHTTPRequestHandler):
    server: _DashboardHTTPServer

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_HEAD(self) -> None:
        self._handle(send_body=False)

    def do_GET(self) -> None:
        self._handle(send_body=True)

    def do_POST(self) -> None:
        self._method_not_allowed()

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, HEAD")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _handle(self, *, send_body: bool) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self._send_static("index.html", send_body=send_body)
                return
            if parsed.path.startswith("/static/"):
                self._send_static(parsed.path.removeprefix("/static/"), send_body=send_body)
                return
            if parsed.path.startswith("/api/"):
                if self.headers.get(DASHBOARD_TOKEN_HEADER) != self.server.api_token:
                    self._send_json({"error": "unauthorized"}, status=HTTPStatus.UNAUTHORIZED, send_body=send_body)
                    return
                result = self._api_response(parsed.path, parse_qs(parsed.query, keep_blank_values=True))
                if isinstance(result, _BinaryResponse):
                    self._send_binary(result, send_body=send_body)
                else:
                    self._send_json(result, send_body=send_body)
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND, send_body=send_body)
        except AlabError as exc:
            self._send_json(
                {"error": exc.code, "reason": exc.reason, "next": exc.next_action},
                status=_http_status_for_alab_error(exc),
                send_body=send_body,
            )
        except Exception as exc:
            self._send_json(
                {"error": "STORAGE_ERROR", "reason": str(exc)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                send_body=send_body,
            )

    def _send_static(self, name: str, *, send_body: bool) -> None:
        parts = Path(name).parts
        if name.startswith("/") or ".." in parts:
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND, send_body=send_body)
            return
        path = STATIC_ROOT
        for part in parts:
            path = path.joinpath(part)
        if not path.is_file():
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND, send_body=send_body)
            return
        data = path.read_bytes()
        suffix = Path(name).suffix
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", STATIC_TYPES.get(suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def _send_json(self, data: Any, *, status: HTTPStatus = HTTPStatus.OK, send_body: bool) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def _send_binary(self, data: _BinaryResponse, *, send_body: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", data.content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{_safe_download_filename(data.filename)}"')
        self.send_header("Content-Length", str(len(data.payload)))
        self.end_headers()
        if send_body:
            self.wfile.write(data.payload)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")

    def _api_response(self, path: str, params: dict[str, list[str]]) -> Any:
        segments = [unquote(part) for part in path.removeprefix("/api/").split("/") if part]
        if segments == ["summary"]:
            return read_summary(self.server.home, self.server.refresh_seconds)
        if segments == ["projects"]:
            limit, offset = _list_limit_offset(params)
            total = count_projects(self.server.home, query=_first(params, "query"))
            return {
                "projects": read_projects(self.server.home, query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if len(segments) == 2 and segments[0] == "projects":
            return read_project_detail(self.server.home, segments[1])
        if segments == ["experiments"]:
            limit, offset = _list_limit_offset(params)
            total = count_experiments(self.server.home, project_id=_first(params, "project"), query=_first(params, "query"))
            return {
                "experiments": read_experiments(self.server.home, project_id=_first(params, "project"), query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if len(segments) == 2 and segments[0] == "experiments":
            return read_experiment_detail(self.server.home, segments[1])
        if segments == ["runs"]:
            limit, offset = _list_limit_offset(params)
            total = count_runs(self.server.home, project_id=_first(params, "project"), exp_id=_first(params, "exp"), query=_first(params, "query"))
            return {
                "runs": read_runs(self.server.home, project_id=_first(params, "project"), exp_id=_first(params, "exp"), query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if len(segments) == 2 and segments[0] == "runs":
            return read_run_detail(self.server.home, segments[1])
        if segments == ["logs"]:
            limit, offset = _list_limit_offset(params)
            total = count_logs(self.server.home, project_id=_first(params, "project"), exp_id=_first(params, "exp"), run_id=_first(params, "run"), query=_first(params, "query"))
            return {
                "logs": read_logs(self.server.home, project_id=_first(params, "project"), exp_id=_first(params, "exp"), run_id=_first(params, "run"), query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if len(segments) == 3 and segments[0] == "logs" and segments[2] == "content":
            return read_log_content(
                self.server.home,
                segments[1],
                offset=_int_param(params, "offset", 0, minimum=0, maximum=10**12),
                limit=_int_param(params, "limit", DEFAULT_CONTENT_CHUNK_BYTES, minimum=1, maximum=MAX_CONTENT_CHUNK_BYTES),
            )
        if len(segments) == 3 and segments[0] == "logs" and segments[2] == "download":
            return read_log_download(self.server.home, segments[1])
        if segments == ["artifacts"]:
            limit, offset = _list_limit_offset(params)
            total = count_artifacts(self.server.home, project_id=_first(params, "project"), exp_id=_first(params, "exp"), run_id=_first(params, "run"), query=_first(params, "query"))
            return {
                "artifacts": read_artifacts(self.server.home, project_id=_first(params, "project"), exp_id=_first(params, "exp"), run_id=_first(params, "run"), query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if len(segments) == 3 and segments[0] == "artifacts" and segments[2] == "preview":
            return read_artifact_preview(self.server.home, segments[1])
        if len(segments) == 3 and segments[0] == "artifacts" and segments[2] == "download":
            return read_artifact_download(self.server.home, segments[1])
        if segments == ["audit"]:
            limit, offset = _list_limit_offset(params)
            total = count_audit(self.server.home, project_id=_first(params, "project"), query=_first(params, "query"))
            return {
                "audit": read_audit(self.server.home, project_id=_first(params, "project"), query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if segments == ["feedback"]:
            limit, offset = _list_limit_offset(params)
            total = count_feedback(self.server.home, query=_first(params, "query"))
            return {
                "feedback": read_feedback(self.server.home, query=_first(params, "query"), limit=limit, offset=offset),
                "page": _page_meta(total, limit, offset),
            }
        if segments == ["system"]:
            return read_system(
                self.server.home,
                cache_limit=_int_param(params, "cache_limit", MAX_LIST_LIMIT, minimum=1, maximum=MAX_LIST_LIMIT),
                cache_offset=_int_param(params, "cache_offset", 0, minimum=0, maximum=10**12),
            )
        raise AlabError("CONTEXT_NOT_FOUND", "dashboard route not found")


@dataclass(frozen=True)
class _BinaryResponse:
    payload: bytes
    filename: str
    content_type: str


def _http_status_for_alab_error(error: AlabError) -> HTTPStatus:
    if error.code in {"AUTH_REQUIRED", "AUTH_DENIED"}:
        return HTTPStatus.UNAUTHORIZED
    if error.code.endswith("_NOT_FOUND") or error.code == "CONTEXT_NOT_FOUND":
        return HTTPStatus.NOT_FOUND
    if error.code in {"CONFIG_INVALID", "SCOPE_VIOLATION", "CONTEXT_CONFLICT"}:
        return HTTPStatus.BAD_REQUEST
    return HTTPStatus.INTERNAL_SERVER_ERROR


def _first(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name)
    return values[0] if values else None


def _int_param(params: dict[str, list[str]], name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = _first(params, name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise AlabError("CONFIG_INVALID", f"{name} must be between {minimum} and {maximum}")
    return value


def _list_limit_offset(params: dict[str, list[str]]) -> tuple[int, int]:
    return (
        _int_param(params, "limit", DEFAULT_LIST_LIMIT, minimum=1, maximum=MAX_LIST_LIMIT),
        _int_param(params, "offset", 0, minimum=0, maximum=10**12),
    )


def _page_meta(total: int, limit: int, offset: int) -> dict[str, int | None]:
    next_offset = offset + limit if offset + limit < total else None
    return {"limit": limit, "offset": offset, "total": total, "next_offset": next_offset}


def read_summary(home: Home, refresh_seconds: int = DEFAULT_REFRESH_SECONDS) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        home_row = one(conn, "SELECT * FROM homes LIMIT 1")
        projects = _count_by(conn, "projects", "status")
        experiments = _count_by(conn, "experiments", "status")
        runs = _count_by(conn, "runs", "status")
        validations = _count_by(conn, "project_validations", "status")
        artifacts = _count_by(conn, "artifacts", "status")
        logs = _count_by(conn, "log_streams", "stream")
        recent_failures = [
            _run_summary(row)
            for row in all_rows(
                conn,
                """
                SELECT r.*, e.metadata_json AS exp_metadata_json
                FROM runs r
                LEFT JOIN experiments e ON e.exp_id = r.exp_id
                WHERE r.status IN ('failed','error','timeout','interrupted')
                ORDER BY r.started_at DESC
                LIMIT 20
                """,
            )
        ]
        recent_activity = [_audit_summary(row) for row in all_rows(conn, "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 20")]
        return {
            "home": _clean_dict(_row(home_row) if home_row else {"path": str(home.path)}),
            "home_path": str(home.path),
            "refresh_seconds": refresh_seconds,
            "counts": {
                "projects": projects,
                "experiments": experiments,
                "runs": runs,
                "validations": validations,
                "artifacts": artifacts,
                "logs": logs,
                "active_locks": _scalar_count(conn, "SELECT COUNT(*) FROM locks"),
                "feedback": _feedback_count(home),
                "cache_entries": _scalar_count(conn, "SELECT COUNT(*) FROM cache_entries WHERE status = 'active'"),
            },
            "recent_failures": recent_failures,
            "recent_activity": recent_activity,
            "projects": read_projects(home, conn=conn, limit=DEFAULT_LIST_LIMIT, offset=0),
            "projects_page": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM projects"), DEFAULT_LIST_LIMIT, 0),
        }
    finally:
        conn.close()


def read_projects(
    home: Home,
    *,
    conn: Any | None = None,
    query: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    owns_conn = conn is None
    if conn is None:
        conn = connect_initialized(home)
    try:
        clauses, params = _project_list_filters(query=query)
        where = _where_sql(clauses)
        if limit is None:
            rows = all_rows(conn, f"SELECT * FROM projects{where} ORDER BY updated_at DESC", tuple(params))
        else:
            rows = all_rows(conn, f"SELECT * FROM projects{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?", (*params, limit, offset))
        return [_project_summary(conn, row) for row in rows]
    finally:
        if owns_conn:
            conn.close()


def count_projects(home: Home, *, query: str | None = None) -> int:
    conn = connect_initialized(home)
    try:
        clauses, params = _project_list_filters(query=query)
        return _scalar_count(conn, f"SELECT COUNT(*) FROM projects{_where_sql(clauses)}", tuple(params))
    finally:
        conn.close()


def read_project_detail(home: Home, project_id: str) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        project = one(conn, "SELECT * FROM projects WHERE project_id = ?", (project_id,))
        if project is None:
            raise AlabError("PROJECT_NOT_FOUND", "project not found")
        list_limit = DEFAULT_LIST_LIMIT
        configs = [
            _config_summary(row)
            for row in all_rows(
                conn,
                "SELECT * FROM project_config_versions WHERE project_id = ? ORDER BY version DESC LIMIT ?",
                (project_id, list_limit),
            )
        ]
        return {
            "project": _project_summary(conn, project),
            "configs": configs,
            "sources": [_source_summary(row) for row in all_rows(conn, "SELECT * FROM sources WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, list_limit))],
            "validations": [_validation_summary(row) for row in all_rows(conn, "SELECT * FROM project_validations WHERE project_id = ? ORDER BY started_at DESC LIMIT ?", (project_id, list_limit))],
            "experiments": read_experiments(home, project_id=project_id, conn=conn, limit=list_limit),
            "runs": read_runs(home, project_id=project_id, conn=conn, limit=list_limit),
            "artifacts": [_artifact_summary(row) for row in all_rows(conn, "SELECT * FROM artifacts WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, list_limit))],
            "logs": [_log_summary(row) for row in all_rows(conn, "SELECT * FROM log_streams WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, list_limit))],
            "annotations": [_annotation_summary(row) for row in all_rows(conn, "SELECT * FROM annotations WHERE project_id = ? ORDER BY updated_at DESC LIMIT ?", (project_id, list_limit))],
            "audit": [_audit_summary(row) for row in all_rows(conn, "SELECT * FROM audit_events WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, list_limit))],
            "pages": {
                "configs": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?", (project_id,)), list_limit, 0),
                "sources": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)), list_limit, 0),
                "validations": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)), list_limit, 0),
                "experiments": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)), list_limit, 0),
                "runs": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM runs WHERE project_id = ?", (project_id,)), list_limit, 0),
                "artifacts": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM artifacts WHERE project_id = ?", (project_id,)), list_limit, 0),
                "logs": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM log_streams WHERE project_id = ?", (project_id,)), list_limit, 0),
                "annotations": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM annotations WHERE project_id = ?", (project_id,)), list_limit, 0),
                "audit": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM audit_events WHERE project_id = ?", (project_id,)), list_limit, 0),
            },
        }
    finally:
        conn.close()


def read_experiments(
    home: Home,
    *,
    project_id: str | None = None,
    conn: Any | None = None,
    query: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    owns_conn = conn is None
    if conn is None:
        conn = connect_initialized(home)
    try:
        clauses, params = _experiment_list_filters(project_id=project_id, query=query)
        where = _where_sql(clauses)
        effective_limit = MAX_LIST_LIMIT if limit is None and project_id is None else limit
        if effective_limit is None:
            rows = all_rows(conn, f"SELECT * FROM experiments{where} ORDER BY updated_at DESC", tuple(params))
        else:
            rows = all_rows(conn, f"SELECT * FROM experiments{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?", (*params, effective_limit, offset))
        return [_experiment_summary(conn, row) for row in rows]
    finally:
        if owns_conn:
            conn.close()


def count_experiments(home: Home, *, project_id: str | None = None, query: str | None = None) -> int:
    conn = connect_initialized(home)
    try:
        clauses, params = _experiment_list_filters(project_id=project_id, query=query)
        return _scalar_count(conn, f"SELECT COUNT(*) FROM experiments{_where_sql(clauses)}", tuple(params))
    finally:
        conn.close()


def read_experiment_detail(home: Home, exp_id: str) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        exp = one(conn, "SELECT * FROM experiments WHERE exp_id = ?", (exp_id,))
        if exp is None:
            raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
        list_limit = DEFAULT_LIST_LIMIT
        return {
            "experiment": _experiment_summary(conn, exp),
            "runs": read_runs(home, exp_id=exp_id, conn=conn, limit=list_limit),
            "submission": _maybe_row_summary(one(conn, "SELECT * FROM experiment_submissions WHERE exp_id = ?", (exp_id,))),
            "tags": [row["tag_slug"] for row in all_rows(conn, "SELECT tag_slug FROM experiment_tags WHERE exp_id = ? ORDER BY tag_slug", (exp_id,))],
            "artifacts": [_artifact_summary(row) for row in all_rows(conn, "SELECT * FROM artifacts WHERE exp_id = ? ORDER BY created_at DESC LIMIT ?", (exp_id, list_limit))],
            "logs": [_log_summary(row) for row in all_rows(conn, "SELECT * FROM log_streams WHERE exp_id = ? ORDER BY created_at DESC LIMIT ?", (exp_id, list_limit))],
            "annotations": [
                _annotation_summary(row)
                for row in all_rows(
                    conn,
                    "SELECT * FROM annotations WHERE project_id = ? AND (target_id = ? OR json_extract(target_json, '$.exp_id') = ?) ORDER BY updated_at DESC LIMIT ?",
                    (exp["project_id"], exp_id, exp_id, list_limit),
                )
            ],
            "audit": [_audit_summary(row) for row in all_rows(conn, "SELECT * FROM audit_events WHERE exp_id = ? ORDER BY created_at DESC LIMIT ?", (exp_id, list_limit))],
            "pages": {
                "runs": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)), list_limit, 0),
                "artifacts": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM artifacts WHERE exp_id = ?", (exp_id,)), list_limit, 0),
                "logs": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM log_streams WHERE exp_id = ?", (exp_id,)), list_limit, 0),
                "annotations": _page_meta(
                    _scalar_count(
                        conn,
                        "SELECT COUNT(*) FROM annotations WHERE project_id = ? AND (target_id = ? OR json_extract(target_json, '$.exp_id') = ?)",
                        (exp["project_id"], exp_id, exp_id),
                    ),
                    list_limit,
                    0,
                ),
                "audit": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM audit_events WHERE exp_id = ?", (exp_id,)), list_limit, 0),
            },
        }
    finally:
        conn.close()


def read_runs(
    home: Home,
    *,
    project_id: str | None = None,
    exp_id: str | None = None,
    conn: Any | None = None,
    query: str | None = None,
    limit: int = MAX_LIST_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    owns_conn = conn is None
    if conn is None:
        conn = connect_initialized(home)
    try:
        clauses, params = _run_list_filters(project_id=project_id, exp_id=exp_id, query=query)
        where = _where_sql(clauses, prefix="WHERE")
        rows = all_rows(
            conn,
            f"""
            SELECT r.*, e.metadata_json AS exp_metadata_json
            FROM runs r LEFT JOIN experiments e ON e.exp_id = r.exp_id
            {where}
            ORDER BY r.started_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [_run_summary(row) for row in rows]
    finally:
        if owns_conn:
            conn.close()


def count_runs(home: Home, *, project_id: str | None = None, exp_id: str | None = None, query: str | None = None) -> int:
    conn = connect_initialized(home)
    try:
        clauses, params = _run_list_filters(project_id=project_id, exp_id=exp_id, query=query)
        return _scalar_count(conn, f"SELECT COUNT(*) FROM runs r{_where_sql(clauses)}", tuple(params))
    finally:
        conn.close()


def read_run_detail(home: Home, run_id: str) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        run = one(
            conn,
            """
            SELECT r.*, e.metadata_json AS exp_metadata_json
            FROM runs r LEFT JOIN experiments e ON e.exp_id = r.exp_id
            WHERE r.run_id = ?
            """,
            (run_id,),
        )
        if run is None:
            raise AlabError("RUN_NOT_FOUND", "run not found")
        list_limit = DEFAULT_LIST_LIMIT
        return {
            "run": _run_summary(run, include_record=True),
            "logs": [_log_summary(row) for row in all_rows(conn, "SELECT * FROM log_streams WHERE run_id = ? ORDER BY stream, created_at LIMIT ?", (run_id, list_limit))],
            "artifacts": [_artifact_summary(row) for row in all_rows(conn, "SELECT * FROM artifacts WHERE run_id = ? ORDER BY relative_path LIMIT ?", (run_id, list_limit))],
            "pages": {
                "logs": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM log_streams WHERE run_id = ?", (run_id,)), list_limit, 0),
                "artifacts": _page_meta(_scalar_count(conn, "SELECT COUNT(*) FROM artifacts WHERE run_id = ?", (run_id,)), list_limit, 0),
            },
        }
    finally:
        conn.close()


def read_logs(
    home: Home,
    *,
    project_id: str | None = None,
    exp_id: str | None = None,
    run_id: str | None = None,
    query: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conn = connect_initialized(home)
    try:
        clauses, params = _log_list_filters(project_id=project_id, exp_id=exp_id, run_id=run_id, query=query)
        rows = all_rows(conn, f"SELECT * FROM log_streams{_where_sql(clauses)} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset))
        return [_log_summary(row) for row in rows]
    finally:
        conn.close()


def count_logs(home: Home, *, project_id: str | None = None, exp_id: str | None = None, run_id: str | None = None, query: str | None = None) -> int:
    conn = connect_initialized(home)
    try:
        clauses, params = _log_list_filters(project_id=project_id, exp_id=exp_id, run_id=run_id, query=query)
        return _scalar_count(conn, f"SELECT COUNT(*) FROM log_streams{_where_sql(clauses)}", tuple(params))
    finally:
        conn.close()


def read_artifacts(
    home: Home,
    *,
    project_id: str | None = None,
    exp_id: str | None = None,
    run_id: str | None = None,
    query: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conn = connect_initialized(home)
    try:
        clauses, params = _artifact_list_filters(project_id=project_id, exp_id=exp_id, run_id=run_id, query=query)
        rows = all_rows(conn, f"SELECT * FROM artifacts{_where_sql(clauses)} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset))
        return [_artifact_summary(row) for row in rows]
    finally:
        conn.close()


def count_artifacts(home: Home, *, project_id: str | None = None, exp_id: str | None = None, run_id: str | None = None, query: str | None = None) -> int:
    conn = connect_initialized(home)
    try:
        clauses, params = _artifact_list_filters(project_id=project_id, exp_id=exp_id, run_id=run_id, query=query)
        return _scalar_count(conn, f"SELECT COUNT(*) FROM artifacts{_where_sql(clauses)}", tuple(params))
    finally:
        conn.close()


def read_log_content(home: Home, log_id: str, *, offset: int, limit: int) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        row = _log_row(conn, log_id)
        path = _stored_path(home, row["project_id"], row["file_path"])
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read(limit)
        return {
            "log": _log_summary(row),
            "offset": offset,
            "limit": limit,
            "size": size,
            "next_offset": offset + len(chunk) if offset + len(chunk) < size else None,
            "content": chunk.decode("utf-8", errors="replace"),
        }
    finally:
        conn.close()


def read_log_download(home: Home, log_id: str) -> _BinaryResponse:
    conn = connect_initialized(home)
    try:
        row = _log_row(conn, log_id)
        payload = _stored_path(home, row["project_id"], row["file_path"]).read_bytes()
        return _BinaryResponse(
            payload=payload,
            filename=f"{row['log_id']}-{row['stream']}.log",
            content_type="text/plain; charset=utf-8",
        )
    finally:
        conn.close()


def read_artifact_preview(home: Home, artifact_id: str) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        row = _artifact_row(conn, artifact_id)
        summary = _artifact_summary(row)
        if row["status"] != "captured" or not row["blob_path"]:
            return {"artifact": summary, "preview": {"kind": "unavailable", "reason": row["status"]}}
        path = _stored_path(home, row["project_id"], row["blob_path"])
        content_type = mimetypes.guess_type(row["relative_path"])[0] or "application/octet-stream"
        size = path.stat().st_size
        if size > MAX_PREVIEW_BYTES:
            return {"artifact": summary, "preview": {"kind": "too_large", "content_type": content_type, "limit": MAX_PREVIEW_BYTES}}
        payload = path.read_bytes()
        if content_type.startswith("text/") or _looks_like_text(payload):
            return {"artifact": summary, "preview": {"kind": "text", "content_type": content_type, "content": payload.decode("utf-8", errors="replace")}}
        if content_type.startswith("image/"):
            encoded = base64.b64encode(payload).decode("ascii")
            return {"artifact": summary, "preview": {"kind": "image", "content_type": content_type, "data_url": f"data:{content_type};base64,{encoded}"}}
        return {"artifact": summary, "preview": {"kind": "binary", "content_type": content_type, "size": size}}
    finally:
        conn.close()


def read_artifact_download(home: Home, artifact_id: str) -> _BinaryResponse:
    conn = connect_initialized(home)
    try:
        row = _artifact_row(conn, artifact_id)
        if row["status"] != "captured" or not row["blob_path"]:
            raise AlabError("ARTIFACT_NOT_FOUND", "artifact bytes were not captured")
        path = _stored_path(home, row["project_id"], row["blob_path"])
        content_type = mimetypes.guess_type(row["relative_path"])[0] or "application/octet-stream"
        return _BinaryResponse(
            payload=path.read_bytes(),
            filename=Path(row["relative_path"]).name or f"{artifact_id}.artifact",
            content_type=content_type,
        )
    finally:
        conn.close()


def read_audit(
    home: Home,
    *,
    project_id: str | None = None,
    query: str | None = None,
    limit: int = MAX_LIST_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    conn = connect_initialized(home)
    try:
        clauses, params = _audit_list_filters(project_id=project_id, query=query)
        return [_audit_summary(row) for row in all_rows(conn, f"SELECT * FROM audit_events{_where_sql(clauses)} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset))]
    finally:
        conn.close()


def count_audit(home: Home, *, project_id: str | None = None, query: str | None = None) -> int:
    conn = connect_initialized(home)
    try:
        clauses, params = _audit_list_filters(project_id=project_id, query=query)
        return _scalar_count(conn, f"SELECT COUNT(*) FROM audit_events{_where_sql(clauses)}", tuple(params))
    finally:
        conn.close()


def _feedback_metadata_rows(home: Home) -> list[tuple[dict[str, Any], Path]]:
    if not home.feedback_path.exists():
        return []
    rows: list[tuple[dict[str, Any], Path]] = []
    for metadata_path in home.feedback_path.glob("*/metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        rows.append((_clean_dict(metadata), metadata_path.with_name("body.md")))
    rows.sort(key=lambda item: str(item[0].get("created_at") or ""), reverse=True)
    return rows


def _read_feedback_body(body_path: Path) -> str:
    try:
        return body_path.read_text(encoding="utf-8") if body_path.exists() else ""
    except (OSError, UnicodeDecodeError):
        return ""


def _feedback_matches(metadata: dict[str, Any], body: str, query: str | None) -> bool:
    if not query:
        return True
    needle = query.casefold()
    metadata_text = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return needle in metadata_text.casefold() or needle in body.casefold()


def read_feedback(home: Home, *, query: str | None = None, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    rows = _feedback_metadata_rows(home)
    entries: list[dict[str, Any]] = []
    if query:
        for metadata, body_path in rows:
            body = _read_feedback_body(body_path)
            if _feedback_matches(metadata, body, query):
                entries.append({"metadata": metadata, "body": body})
        return entries[offset : offset + limit] if limit is not None else entries
    paged_rows = rows[offset : offset + limit] if limit is not None else rows
    for metadata, body_path in paged_rows:
        entries.append({"metadata": metadata, "body": _read_feedback_body(body_path)})
    return entries


def count_feedback(home: Home, *, query: str | None = None) -> int:
    rows = _feedback_metadata_rows(home)
    if not query:
        return len(rows)
    total = 0
    for metadata, body_path in rows:
        if _feedback_matches(metadata, _read_feedback_body(body_path), query):
            total += 1
    return total


def read_system(home: Home, *, cache_limit: int = MAX_LIST_LIMIT, cache_offset: int = 0) -> dict[str, Any]:
    conn = connect_initialized(home)
    try:
        home_row = one(conn, "SELECT * FROM homes LIMIT 1")
        cache_total = _scalar_count(conn, "SELECT COUNT(*) FROM cache_entries")
        return {
            "home": _clean_dict(_row(home_row) if home_row else {"path": str(home.path)}),
            "global_config": _clean_dict(load_global_config(home.config_path)),
            "locks": [_clean_dict(_row(row)) for row in all_rows(conn, "SELECT * FROM locks ORDER BY expires_at")],
            "capabilities": [_clean_dict(_row(row)) for row in all_rows(conn, "SELECT * FROM runtime_capabilities ORDER BY checked_at DESC")],
            "catalogs": [_clean_dict(_row(row)) for row in all_rows(conn, "SELECT * FROM catalogs ORDER BY updated_at DESC")],
            "cache_entries": [_clean_dict(_row(row)) for row in all_rows(conn, "SELECT * FROM cache_entries ORDER BY COALESCE(last_used_at, created_at) DESC LIMIT ? OFFSET ?", (cache_limit, cache_offset))],
            "cache_entries_page": _page_meta(cache_total, cache_limit, cache_offset),
            "feedback_count": _feedback_count(home),
        }
    finally:
        conn.close()


def _where_sql(clauses: list[str], *, prefix: str = "WHERE") -> str:
    return f" {prefix} {' AND '.join(clauses)}" if clauses else ""


def _like_params(query: str | None, count: int) -> list[str]:
    return [f"%{query}%"] * count if query else []


def _project_list_filters(*, query: str | None) -> tuple[list[str], list[Any]]:
    if not query:
        return [], []
    like = _like_params(query, 5)
    return ["(project_id LIKE ? OR status LIKE ? OR canonical_repo_path LIKE ? OR control_path LIKE ? OR active_validation_id LIKE ?)"], like


def _experiment_list_filters(*, project_id: str | None, query: str | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if query:
        clauses.append("(exp_id LIKE ? OR source_id LIKE ? OR branch_name LIKE ? OR metadata_json LIKE ?)")
        params.extend(_like_params(query, 4))
    return clauses, params


def _run_list_filters(*, project_id: str | None, exp_id: str | None, query: str | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("r.project_id = ?")
        params.append(project_id)
    if exp_id:
        clauses.append("r.exp_id = ?")
        params.append(exp_id)
    if query:
        clauses.append("(r.run_id LIKE ? OR r.exp_id LIKE ? OR r.project_id LIKE ? OR r.commit_sha LIKE ? OR r.status LIKE ?)")
        params.extend(_like_params(query, 5))
    return clauses, params


def _log_list_filters(*, project_id: str | None, exp_id: str | None, run_id: str | None, query: str | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if exp_id:
        clauses.append("exp_id = ?")
        params.append(exp_id)
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if query:
        clauses.append("(log_id LIKE ? OR stream LIKE ? OR exp_id LIKE ? OR run_id LIKE ? OR project_id LIKE ? OR preview_text LIKE ?)")
        params.extend(_like_params(query, 6))
    return clauses, params


def _artifact_list_filters(*, project_id: str | None, exp_id: str | None, run_id: str | None, query: str | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if exp_id:
        clauses.append("exp_id = ?")
        params.append(exp_id)
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if query:
        clauses.append("(artifact_id LIKE ? OR relative_path LIKE ? OR exp_id LIKE ? OR run_id LIKE ? OR project_id LIKE ? OR status LIKE ?)")
        params.extend(_like_params(query, 6))
    return clauses, params


def _audit_list_filters(*, project_id: str | None, query: str | None) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if query:
        clauses.append("(audit_id LIKE ? OR object_id LIKE ? OR action LIKE ? OR object_type LIKE ?)")
        params.extend(_like_params(query, 4))
    return clauses, params


def _row(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _maybe_row_summary(row: Any) -> dict[str, Any] | None:
    return _clean_dict(_row(row)) if row is not None else None


def _count_by(conn: Any, table: str, column: str) -> dict[str, int]:
    rows = all_rows(conn, f"SELECT {column} AS name, COUNT(*) AS count FROM {table} GROUP BY {column} ORDER BY {column}")
    return {str(row["name"]): int(row["count"]) for row in rows}


def _scalar_count(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = one(conn, sql, params)
    return int(row[0]) if row is not None else 0


def _feedback_count(home: Home) -> int:
    return len(list(home.feedback_path.glob("*/metadata.json"))) if home.feedback_path.exists() else 0


def _project_summary(conn: Any, row: Any) -> dict[str, Any]:
    config_row = None
    if row["latest_attempted_config_version"] is not None:
        config_row = one(
            conn,
            "SELECT * FROM project_config_versions WHERE project_id = ? AND version = ?",
            (row["project_id"], row["latest_attempted_config_version"]),
        )
    config = _config_json(config_row)
    direction = ((config or {}).get("reward") or {}).get("direction", "maximize")
    best = _project_best_run(conn, row["project_id"], direction=direction)
    counts = {
        "sources": _scalar_count(conn, "SELECT COUNT(*) FROM sources WHERE project_id = ?", (row["project_id"],)),
        "experiments": _scalar_count(conn, "SELECT COUNT(*) FROM experiments WHERE project_id = ?", (row["project_id"],)),
        "open_experiments": _scalar_count(conn, "SELECT COUNT(*) FROM experiments WHERE project_id = ? AND status = 'open'", (row["project_id"],)),
        "runs": _scalar_count(conn, "SELECT COUNT(*) FROM runs WHERE project_id = ?", (row["project_id"],)),
        "failed_runs": _scalar_count(conn, "SELECT COUNT(*) FROM runs WHERE project_id = ? AND status IN ('failed','error','timeout','interrupted')", (row["project_id"],)),
        "artifacts": _scalar_count(conn, "SELECT COUNT(*) FROM artifacts WHERE project_id = ?", (row["project_id"],)),
        "logs": _scalar_count(conn, "SELECT COUNT(*) FROM log_streams WHERE project_id = ?", (row["project_id"],)),
    }
    return _clean_dict(
        {
            **_row(row),
            "name": ((config or {}).get("project") or {}).get("name"),
            "task": ((config or {}).get("project") or {}).get("task"),
            "goal": ((config or {}).get("project") or {}).get("goal"),
            "runner_type": ((config or {}).get("runner") or {}).get("type"),
            "reward_type": ((config or {}).get("reward") or {}).get("type"),
            "reward_direction": direction,
            "reference_metrics": ((config or {}).get("metrics") or {}).get("reference") or [],
            "visibility_scope": ((config or {}).get("visibility") or {}).get("scope"),
            "counts": counts,
            "best_run": _run_summary(best) if best else None,
        }
    )


def _project_best_run(conn: Any, project_id: str, *, direction: str) -> Any | None:
    order = "ASC" if direction == "minimize" else "DESC"
    return one(
        conn,
        f"""
        SELECT r.*, e.metadata_json AS exp_metadata_json
        FROM runs r LEFT JOIN experiments e ON e.exp_id = r.exp_id
        WHERE r.project_id = ? AND r.reward_value IS NOT NULL AND r.archive_status = 'active'
        ORDER BY r.reward_value {order}, r.ended_at DESC
        LIMIT 1
        """,
        (project_id,),
    )


def _config_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    config = _config_json(row)
    data["config"] = config
    data.pop("canonical_config_json", None)
    return _clean_dict(data)


def _config_json(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    try:
        return _sanitize_config(project_config_json_obj(row["canonical_config_json"]))
    except Exception:
        return {"invalid": True}


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(config)
    secret_env = sanitized.get("secret_env")
    if isinstance(secret_env, dict):
        sanitized["secret_env"] = {
            name: {"fingerprint": marker.get("fingerprint") if isinstance(marker, dict) else None}
            for name, marker in secret_env.items()
        }
    return sanitized


def _source_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    data["origin_metadata"] = _json_or_none(data.pop("origin_metadata_json", None))
    return _clean_dict(data)


def _experiment_summary(conn: Any, row: Any) -> dict[str, Any]:
    metadata = _json_or_none(row["metadata_json"]) or {}
    policy = _json_or_none(row["policy_json"]) or {}
    tags = [tag["tag_slug"] for tag in all_rows(conn, "SELECT tag_slug FROM experiment_tags WHERE exp_id = ? ORDER BY tag_slug", (row["exp_id"],))]
    latest = one(
        conn,
        "SELECT r.*, ? AS exp_metadata_json FROM runs r WHERE r.run_id = ?",
        (row["metadata_json"], row["latest_run_id"]),
    ) if row["latest_run_id"] else None
    final = one(
        conn,
        "SELECT r.*, ? AS exp_metadata_json FROM runs r WHERE r.run_id = ?",
        (row["metadata_json"], row["final_run_id"]),
    ) if row["final_run_id"] else None
    run_count = _scalar_count(conn, "SELECT COUNT(*) FROM runs WHERE exp_id = ?", (row["exp_id"],))
    return _clean_dict(
        {
            **_row(row),
            "name": metadata.get("name"),
            "goal": metadata.get("goal"),
            "metadata": metadata,
            "policy": policy,
            "tags": tags,
            "run_count": run_count,
            "latest_run": _run_summary(latest) if latest else None,
            "final_run": _run_summary(final) if final else None,
        }
    )


def _run_summary(row: Any, *, include_record: bool = False) -> dict[str, Any]:
    data = _row(row)
    record = _json_or_none(data.pop("record_json", None)) or {}
    data["exp_name"] = (_json_or_none(data.pop("exp_metadata_json", None)) or {}).get("name")
    data["failure_reason"] = record.get("failure_reason") or record.get("error") or record.get("reason")
    data["warning_codes"] = record.get("warning_codes") or record.get("warnings") or []
    data["metrics"] = record.get("metrics") or {}
    data["runner"] = record.get("runner") or record.get("runner_type")
    if include_record:
        data["record"] = _clean_dict(record)
    return _clean_dict(data)


def _validation_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    data["record"] = _clean_dict(_json_or_none(data.pop("record_json", None)) or {})
    return _clean_dict(data)


def _artifact_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    data.pop("blob_path", None)
    return _clean_dict(data)


def _log_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    data.pop("file_path", None)
    data["hidden"] = bool(data.get("hidden"))
    data["truncated"] = bool(data.get("truncated"))
    return _clean_dict(data)


def _annotation_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    data["target"] = _json_or_none(data.pop("target_json", None))
    data["visibility"] = _json_or_none(data.pop("visibility_json", None))
    return _clean_dict(data)


def _audit_summary(row: Any) -> dict[str, Any]:
    data = _row(row)
    data["cascade"] = bool(data.get("cascade"))
    data["deleted_ids"] = _json_or_none(data.pop("deleted_ids_json", None))
    data["metadata"] = _json_or_none(data.pop("metadata_json", None))
    return _clean_dict(data)


def _json_or_none(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _clean_dict(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            if key in {"salt", "verifier_hash"}:
                continue
            if key == "secret_env" and isinstance(child, dict):
                clean[key] = {
                    name: {"fingerprint": marker.get("fingerprint") if isinstance(marker, dict) else None}
                    for name, marker in child.items()
                }
                continue
            if isinstance(child, bytes):
                continue
            clean[key] = _clean_dict(child)
        return clean
    if isinstance(value, list):
        return [_clean_dict(item) for item in value]
    if isinstance(value, bytes):
        return None
    return value


def _log_row(conn: Any, log_id: str) -> Any:
    row = one(conn, "SELECT * FROM log_streams WHERE log_id = ?", (log_id,))
    if row is None:
        raise AlabError("LOG_NOT_FOUND", "log not found")
    return row


def _artifact_row(conn: Any, artifact_id: str) -> Any:
    row = one(conn, "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
    if row is None:
        raise AlabError("ARTIFACT_NOT_FOUND", "artifact not found")
    return row


def _stored_path(home: Home, project_id: str, relative: str) -> Path:
    base = (home.projects_path / project_id / "artifacts").resolve()
    candidate = (base / relative).resolve()
    if not candidate.is_relative_to(base):
        raise AlabError("STORAGE_ERROR", "stored file path escapes project artifact store")
    return candidate


def _looks_like_text(payload: bytes) -> bool:
    if b"\0" in payload:
        return False
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _safe_download_filename(filename: str) -> str:
    cleaned = "".join(
        ch if ch.isascii() and ch not in {'"', "\\", "\r", "\n"} and (ch.isalnum() or ch in ".-_") else "_"
        for ch in filename
    )
    cleaned = cleaned.strip("._")
    return cleaned or "alab-download"
