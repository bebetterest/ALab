from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from typing import Annotated

import typer

from .auth import read_token, token_permission_warning, verify_raw_credential
from .configs import load_global_config, project_config_json_obj
from .context import detect_context
from .db import connect_initialized, one
from .errors import AlabError, error_exit_code
from .home import resolve_home
from .registry import COMMANDS, CommandSpec, match_command
from .rendering import ResultBlock, error_block, render_text
from .services import GlobalOptions, Request


@dataclass
class ParsedGlobals:
    argv: list[str]
    home: str | None = None
    output: str = "text"
    key: str | None = None
    key_source: str | None = None


PathTuple = tuple[str, ...]

app = typer.Typer(
    add_completion=False,
    add_help_option=False,
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True, "help_option_names": []},
)


GLOBAL_PUBLIC: set[PathTuple] = {
    ("help",),
    ("auth", "init"),
    ("config", "show"),
    ("config", "set"),
    ("config", "reset"),
    ("config", "validate"),
    ("context", "show"),
    ("context", "repair"),
    ("feedback",),
}

GLOBAL_CONFIG_REPAIR: set[PathTuple] = {
    ("auth", "init"),
    ("config", "show"),
    ("config", "set"),
    ("config", "reset"),
    ("config", "validate"),
    ("feedback",),
}

PUBLIC_PROJECT: set[PathTuple] = {
    ("status",),
}

PUBLIC_PROJECT_WHEN_ENABLED: set[PathTuple] = {
    ("exp", "create"),
}

EXPERIMENT_TOKEN: set[PathTuple] = {
    ("status",),
    ("run",),
    ("submit",),
    ("exp", "checkout"),
    ("exp", "tag", "add"),
    ("exp", "tag", "remove"),
    ("exp", "tag", "list"),
    ("annotate", "add"),
    ("annotate", "edit"),
    ("annotate", "archive"),
    ("annotate", "unarchive"),
    ("annotate", "remove"),
}

OBSERVE_READ: set[PathTuple] = {
    ("exp", "list"),
    ("exp", "search"),
    ("exp", "show"),
    ("exp", "best"),
    ("observe", "experiments", "list"),
    ("observe", "experiments", "search"),
    ("observe", "experiments", "show"),
    ("observe", "experiments", "best"),
    ("observe", "runs", "list"),
    ("observe", "runs", "show"),
    ("observe", "artifacts", "list"),
    ("observe", "artifacts", "show"),
    ("observe", "artifacts", "export"),
    ("observe", "logs", "list"),
    ("observe", "logs", "show"),
    ("observe", "logs", "export"),
    ("observe", "annotations", "list"),
    ("observe", "annotations", "show"),
    ("runs", "list"),
    ("runs", "show"),
    ("artifacts", "list"),
    ("artifacts", "show"),
    ("artifacts", "export"),
    ("logs", "list"),
    ("logs", "show"),
    ("logs", "export"),
    ("annotations", "list"),
    ("annotations", "show"),
}

OBSERVE_TOKEN_LIFECYCLE: set[PathTuple] = {
    ("observe", "runs", "archive"),
    ("observe", "runs", "unarchive"),
    ("observe", "artifacts", "archive"),
    ("observe", "artifacts", "unarchive"),
    ("observe", "logs", "archive"),
    ("observe", "logs", "unarchive"),
    ("runs", "archive"),
    ("runs", "unarchive"),
    ("artifacts", "archive"),
    ("artifacts", "unarchive"),
    ("logs", "archive"),
    ("logs", "unarchive"),
}

INSPECTION_TOKEN: set[PathTuple] = {
    ("status",),
    ("exp", "checkout", "remove"),
}


HELP_OPTIONS = {"--all", "--explain"}


def pre_scan(argv: list[str]) -> ParsedGlobals:
    cleaned: list[str] = []
    parsed = ParsedGlobals(argv=cleaned)
    i = 0
    stop = False
    seen: set[str] = set()
    while i < len(argv):
        item = argv[i]
        if item == "--":
            stop = True
            cleaned.extend(argv[i:])
            break
        if not stop and item in {"--home", "--output", "--key"}:
            if item in seen:
                raise AlabError("CONFIG_INVALID", f"duplicate global option {item}")
            if item == "--key" and "--key-stdin" in seen:
                raise AlabError("CONFIG_INVALID", "--key conflicts with --key-stdin")
            seen.add(item)
            if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                raise AlabError("CONFIG_INVALID", f"{item} requires a value")
            value = argv[i + 1]
            if value == "":
                raise AlabError("CONFIG_INVALID", f"{item} requires a non-empty value")
            if item == "--home":
                parsed.home = value
            elif item == "--output":
                if value not in {"text", "rich"}:
                    raise AlabError("CONFIG_INVALID", "--output must be text or rich")
                parsed.output = value
            elif item == "--key":
                parsed.key = value
                parsed.key_source = "explicit"
            i += 2
            continue
        if not stop and item == "--key-stdin":
            if "--key-stdin" in seen or "--key" in seen:
                raise AlabError("CONFIG_INVALID", "--key conflicts with --key-stdin")
            seen.add(item)
            raw = sys.stdin.read()
            if raw.endswith("\n"):
                raw = raw[:-1]
            if not raw or "\n" in raw or "\0" in raw:
                raise AlabError("CONFIG_INVALID", "--key-stdin requires a non-empty single-line value")
            parsed.key = raw
            parsed.key_source = "explicit"
            i += 1
            continue
        cleaned.append(item)
        i += 1
    return parsed


def _option_value(args: list[str], name: str) -> str | None:
    for idx, item in enumerate(args):
        if item == name:
            if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
                raise AlabError("CONFIG_INVALID", f"{name} requires a value")
            if args[idx + 1] == "":
                raise AlabError("CONFIG_INVALID", f"{name} requires a non-empty value")
            return args[idx + 1]
    return None


def _safe_context(home) -> object | None:
    try:
        if not home.db_path.exists():
            return None
        return detect_context(home)
    except AlabError:
        raise
    except Exception:
        return None


def _requested_project_id(req: Request, args: list[str] | None = None) -> str | None:
    return _option_value(args or [], "--project") or (req.context.project_id if req.context else None)


def _has_context_token(req: Request, token_mode: str) -> bool:
    if not req.context:
        return False
    if token_mode == "worktree" and req.context.context_type != "experiment":
        return False
    if token_mode == "inspection" and req.context.context_type != "inspection":
        return False
    try:
        conn = connect_initialized(req.globals.home)
        try:
            token = read_token(req.context.path)
            verify_raw_credential(
                conn,
                token,
                required="token",
                project_id=req.context.project_id,
                exp_id=req.context.exp_id,
                token_mode=token_mode,
                path_hash=req.context.path_hash,
            )
            return True
        finally:
            conn.close()
    except AlabError:
        return False


def _public_exp_create_enabled(req: Request, args: list[str] | None = None) -> bool:
    project_id = _requested_project_id(req, args)
    if project_id is None:
        return False
    try:
        conn = connect_initialized(req.globals.home)
        try:
            project = one(conn, "SELECT * FROM projects WHERE project_id = ?", (project_id,))
            if project is None or project["status"] != "valid":
                return False
            version = project["active_valid_config_version"]
            if version is None:
                return False
            row = one(
                conn,
                "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
                (project_id, version),
            )
            if row is None:
                return False
            config = project_config_json_obj(row["canonical_config_json"])
            return bool(config.get("project", {}).get("allow_public_exp_create", True))
        finally:
            conn.close()
    except AlabError:
        return False


def _admin_actor_scope(req: Request) -> str | None:
    if not req.globals.key or req.actor is None:
        return None
    if req.actor.actor_type == "root":
        return "root"
    if req.actor.actor_type == "admin":
        return "admin"
    return None


def _admin_project_mismatch(req: Request, args: list[str] | None) -> bool:
    if req.actor is None or req.actor.actor_type != "admin" or not req.actor.project_id:
        return False
    requested = _requested_project_id(req, args)
    return bool(requested and requested != req.actor.project_id)


def _context_project_conflict(req: Request, args: list[str] | None) -> bool:
    requested = _option_value(args or [], "--project")
    return bool(requested and req.context and req.context.project_id and requested != req.context.project_id)


def _availability(spec: CommandSpec, req: Request, args: list[str] | None = None) -> tuple[bool, str | None, str | None]:
    if _context_project_conflict(req, args):
        return False, "explicit project conflicts with current context", "leave the context or use the matching project id"
    path = spec.path
    admin_scope = _admin_actor_scope(req)
    if admin_scope == "root":
        if spec.credential == "token":
            if req.context and req.context.context_type == "experiment" and _has_context_token(req, "worktree"):
                return True, None, "worktree-token"
            return (
                False,
                "experiment worktree token context required",
                "run from an experiment worktree",
            )
        return True, None, "root"
    if admin_scope == "admin":
        if spec.credential == "root":
            return False, "root credential required", "use a root key"
        if spec.credential == "token":
            if req.context and req.context.context_type == "experiment" and _has_context_token(req, "worktree"):
                return True, None, "worktree-token"
            return (
                False,
                "experiment worktree token context required",
                "run from an experiment worktree",
            )
        if _admin_project_mismatch(req, args):
            if path in PUBLIC_PROJECT and _requested_project_id(req, args):
                return True, None, "public-project"
            if path in PUBLIC_PROJECT_WHEN_ENABLED and _public_exp_create_enabled(req, args):
                return True, None, "public-project"
            if spec.credential in {"admin", "public_or_admin", "token_or_admin"}:
                return False, "project admin credential does not match requested project", "use a matching project admin key or root key"
        return True, None, "project-admin"
    if path in GLOBAL_PUBLIC:
        return True, None, "global"
    if req.context is None:
        if path in PUBLIC_PROJECT and _requested_project_id(req, args):
            return True, None, "public-project"
        if path in PUBLIC_PROJECT_WHEN_ENABLED and _public_exp_create_enabled(req, args):
            return True, None, "public-project"
        return False, "project, experiment, inspection, or explicit credential required", "use alab help --all or pass an explicit key"
    if req.context.context_type == "project":
        if path in PUBLIC_PROJECT:
            return True, None, "public-project"
        if path in PUBLIC_PROJECT_WHEN_ENABLED and _public_exp_create_enabled(req, args):
            return True, None, "public-project"
        return False, "project admin or root credential required", "pass --key or --key-stdin"
    if req.context.context_type == "experiment":
        if not _has_context_token(req, "worktree"):
            return False, "valid experiment token required", "repair context or restore token"
        if path in EXPERIMENT_TOKEN or path in OBSERVE_READ or path in OBSERVE_TOKEN_LIFECYCLE:
            return True, None, "worktree-token"
        if path in PUBLIC_PROJECT_WHEN_ENABLED and _public_exp_create_enabled(req, args):
            return True, None, "public-project"
        return False, "command is not exposed to experiment tokens", "pass an explicit project admin/root key when appropriate"
    if req.context.context_type == "inspection":
        if not _has_context_token(req, "inspection"):
            return False, "valid inspection token required", "repair context or recreate the inspection checkout"
        if path in INSPECTION_TOKEN or path in OBSERVE_READ:
            return True, None, "inspection-token"
        return False, "command is not exposed to inspection tokens", "pass an explicit project admin/root key when appropriate"
    return False, "credential or context required", "use an explicit key or matching context"


def _credential_source(req: Request) -> str:
    if req.globals.key and req.actor:
        return "explicit-root" if req.actor.actor_type == "root" else "explicit-admin" if req.actor.actor_type == "admin" else "explicit-token"
    if req.context and req.context.context_type == "project":
        return "public"
    if req.context and req.context.context_type in {"experiment", "inspection"}:
        return "context-token"
    return "none"


def _credential_scope(req: Request) -> str:
    if req.actor:
        if req.actor.actor_type == "token" and req.actor.token_mode:
            return f"token:{req.actor.token_mode}"
        return req.actor.actor_type
    if req.context and req.context.context_type == "experiment":
        return "token:worktree"
    if req.context and req.context.context_type == "inspection":
        return "token:inspection"
    return "none"


def _parse_help_options(options: list[str]) -> tuple[bool, bool]:
    seen: set[str] = set()
    for item in options:
        if item not in HELP_OPTIONS:
            raise AlabError("CONFIG_INVALID", f"invalid help option {item}")
        if item in seen:
            raise AlabError("CONFIG_INVALID", f"duplicate help option {item}")
        seen.add(item)
    return "--all" in seen, "--explain" in seen


def _help_request(argv: list[str]) -> tuple[bool, bool, list[tuple[CommandSpec, list[str] | None]] | None, bool] | None:
    if not argv:
        return False, False, None, False
    if argv[0] == "help":
        all_commands, explain = _parse_help_options(argv[1:])
        return all_commands, explain, None, False
    if argv[0] == "--help":
        all_commands, explain = _parse_help_options(argv[1:])
        return all_commands, explain, None, False

    stop_at = argv.index("--") if "--" in argv else len(argv)
    prefix = argv[:stop_at]
    suffix = argv[stop_at:]
    if "--help" not in prefix:
        return None
    if prefix.count("--help") > 1:
        raise AlabError("CONFIG_INVALID", "duplicate help option --help")
    for option in HELP_OPTIONS:
        if prefix.count(option) > 1:
            raise AlabError("CONFIG_INVALID", f"duplicate help option {option}")
    selector = [item for item in prefix if item not in HELP_OPTIONS and item != "--help"]
    all_commands = "--all" in prefix
    explain = "--explain" in prefix
    if not selector:
        return all_commands, explain, None, False
    spec, rest = match_command(selector + suffix)
    if spec is None:
        raise AlabError("CONFIG_INVALID", "invalid help selector")
    return all_commands, explain, [(spec, rest)], True


def _is_help_request(argv: list[str]) -> bool:
    if not argv or argv[0] in {"help", "--help"}:
        return True
    stop_at = argv.index("--") if "--" in argv else len(argv)
    return "--help" in argv[:stop_at]


def help_blocks(
    req: Request,
    *,
    all_commands: bool = False,
    explain: bool = False,
    commands: list[tuple[CommandSpec, list[str] | None]] | None = None,
    include_locked_selected: bool = False,
) -> list[ResultBlock]:
    context_type = req.context.context_type if req.context else "none"
    credential_source = _credential_source(req)
    blocks = [
        ResultBlock(
            "help",
            [
                ("context type", context_type),
                ("credential source", credential_source),
                ("credential scope", _credential_scope(req)),
                ("project id", req.context.project_id if req.context else None),
                ("exp id", req.context.exp_id if req.context else None),
                ("mode", "all" if all_commands else "available"),
                ("next", ["alab auth init"] if context_type == "none" else ["alab status"]),
            ],
        )
    ]
    selected = commands or [(spec, None) for spec in COMMANDS]
    command_rows: list[tuple[bool, ResultBlock]] = []
    for spec, command_args in selected:
        available, locked_reason, hint_or_source = _availability(spec, req, command_args)
        if not available and not all_commands and not include_locked_selected:
            continue
        command_rows.append(
            (
                available,
                ResultBlock(
                    "help_command",
                    [
                        ("command", " ".join(spec.path)),
                        ("available", available),
                        ("locked reason", None if available else locked_reason),
                        ("unlock hint", None if available else hint_or_source),
                        ("capability source", hint_or_source if explain else None),
                        ("summary", spec.summary),
                    ],
                ),
            )
        )
    if all_commands and commands is None:
        command_rows.sort(key=lambda item: not item[0])
    blocks.extend(block for _available, block in command_rows)
    return blocks


def _context_token_warning_blocks(req: Request) -> list[ResultBlock]:
    if req.context is None or req.context.context_type not in {"experiment", "inspection"}:
        return []
    warning = token_permission_warning(req.context.path)
    if warning is None:
        return []
    return [
        ResultBlock(
            "warning",
            [
                ("warning code", warning),
                ("warning reason", "token file permissions are broader than 0600"),
            ],
        )
    ]


def _with_context_token_warnings(req: Request, blocks: list[ResultBlock]) -> list[ResultBlock]:
    return [*blocks, *_context_token_warning_blocks(req)]


def build_base_request(parsed: ParsedGlobals) -> Request:
    home = resolve_home(parsed.home)
    globals_ = GlobalOptions(home=home, output=parsed.output, key=parsed.key, key_source=parsed.key_source)
    return Request(globals=globals_, context=None, actor=None)


def hydrate_request(req: Request) -> Request:
    context = _safe_context(req.globals.home)
    actor = None
    if req.globals.key and req.globals.home.db_path.exists():
        conn = connect_initialized(req.globals.home)
        try:
            actor = verify_raw_credential(conn, req.globals.key)
        finally:
            conn.close()
    return Request(globals=req.globals, context=context, actor=actor)


def build_request(parsed: ParsedGlobals) -> Request:
    return hydrate_request(build_base_request(parsed))


def preflight(spec: CommandSpec, req: Request, args: list[str] | None = None) -> None:
    if _context_project_conflict(req, args):
        raise AlabError("CONTEXT_CONFLICT", "explicit --project conflicts with current ALab context")
    available, _reason, _hint = _availability(spec, req, args)
    if available:
        return
    raise AlabError("COMMAND_UNAVAILABLE", "command is not available in the current context")


def enforce_global_config_valid(spec_path: PathTuple, req: Request) -> None:
    if spec_path in GLOBAL_CONFIG_REPAIR:
        return
    load_global_config(req.globals.home.config_path)


def infer_result_exit_code(blocks: list[ResultBlock]) -> int:
    for block in blocks:
        fields = dict(block.fields)
        saved_failure = "error code" in fields
        if block.object_type == "run" and saved_failure and fields.get("run status") not in {None, "passed"}:
            return 1
        if block.object_type == "validation" and saved_failure and fields.get("validation status") not in {None, "passed"}:
            return 1
        if block.object_type in {"project_config", "project_env", "project_secret"} and saved_failure and fields.get("validation status") not in {None, "passed", "skipped", "inherited", "dry-run"}:
            return 1
        if block.object_type == "project" and saved_failure and fields.get("validation status") not in {None, "passed", "skipped"}:
            return 1
        if block.object_type == "submission" and fields.get("submit accepted") is False:
            return 1
    return 0


def run(argv: list[str]) -> int:
    try:
        parsed = pre_scan(argv)
        base_req = build_base_request(parsed)
        if _is_help_request(parsed.argv):
            enforce_global_config_valid(("help",), base_req)
            req = build_request(parsed)
            help_request = _help_request(parsed.argv)
            if help_request is None:
                raise AlabError("CONFIG_INVALID", "invalid help selector")
            all_commands, explain, commands, include_locked_selected = help_request
            sys.stdout.write(
                render_text(
                    _with_context_token_warnings(
                        req,
                        help_blocks(
                            req,
                            all_commands=all_commands,
                            explain=explain,
                            commands=commands,
                            include_locked_selected=include_locked_selected,
                        ),
                    )
                )
            )
            return 0
        spec, rest = match_command(parsed.argv)
        if spec is None:
            raise AlabError("COMMAND_UNAVAILABLE", "unknown or unavailable command")
        enforce_global_config_valid(spec.path, base_req)
        req = build_request(parsed)
        preflight(spec, req, rest)
        blocks = spec.handler(rest, req)
        blocks = _with_context_token_warnings(req, blocks)
        sys.stdout.write(render_text(blocks))
        return infer_result_exit_code(blocks)
    except AlabError as exc:
        sys.stderr.write(
            render_text(
                [
                    error_block(
                        message=exc.message,
                        code=exc.code,
                        exit_code=exc.exit_code or error_exit_code(exc.code),
                        reason=exc.reason,
                        next_action=exc.next_action,
                    )
                ]
            )
        )
        if os.environ.get("ALAB_DEBUG") == "1" and (exc.exit_code or 5) == 5:
            traceback.print_exc(file=sys.stderr)
        return exc.exit_code or error_exit_code(exc.code)
    except Exception as exc:
        sys.stderr.write(
            render_text(
                [
                    error_block(
                        message="Command failed.",
                        code="STORAGE_ERROR",
                        exit_code=5,
                        reason=str(exc),
                        next_action=None,
                    )
                ]
            )
        )
        if os.environ.get("ALAB_DEBUG") == "1":
            traceback.print_exc(file=sys.stderr)
        return 5


@app.callback(invoke_without_command=True)
def _typer_entry(ctx: typer.Context, args: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    raise typer.Exit(run([*(args or []), *ctx.args]))


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        app(prog_name="alab")
        return
    raise SystemExit(run(list(argv)))
