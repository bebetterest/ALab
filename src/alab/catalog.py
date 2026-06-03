from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from .configs import project_config_json_obj
from .db import Database, all_rows, canonical_json, one
from .errors import AlabError
from .home import Home
from .proc import run_cmd
from .rendering import ResultBlock
from .service_args import (
    _full_commit_sha_filter,
    command_arg,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_audit import audit
from .service_auth import require_actor, require_home
from .service_contracts import catalog_metadata_json_obj
from .service_models import Request
from .service_text import _lifecycle_reason
from .timeutil import utc_now

SKYDISCOVER_ORIGIN_URL = "https://github.com/skydiscover-ai/skydiscover.git"


def _catalog_local_path(home: Home) -> Path:
    return home.sources_path / "skydiscover"


def _catalog_git(repo: Path, args: list[str], reason: str):
    try:
        return run_cmd(["git", *args], cwd=repo if repo.exists() else None)
    except AlabError as exc:
        if exc.code == "GIT_ERROR":
            raise AlabError("CONFIG_INVALID", f"{reason}: {exc.reason}") from exc
        raise


def _resolve_catalog_commit(repo: Path, *, ref: str | None, commit: str | None) -> tuple[str, str]:
    if ref and commit:
        raise AlabError("CONFIG_INVALID", "--ref conflicts with --commit")
    commit = _full_commit_sha_filter(commit)
    _catalog_git(repo, ["fetch", "--quiet", "--tags", "origin"], "catalog fetch failed")
    if commit:
        _catalog_git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"], "catalog commit does not exist")
        return commit.lower(), commit
    requested = ref or "main"
    candidates = [f"origin/{requested}", requested]
    for candidate in candidates:
        completed = run_cmd(["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"], cwd=repo, check=False)
        if completed.returncode == 0:
            return completed.stdout.decode("utf-8", errors="replace").strip(), requested
    raise AlabError("CONFIG_INVALID", f"catalog ref does not resolve to a commit: {requested}")


def _active_catalog_row(conn):
    row = one(conn, "SELECT * FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'")
    if row is None:
        raise AlabError("CATALOG_NOT_FOUND", "active SkyDiscover catalog not found", "alab catalog skydiscover add")
    catalog_metadata_json_obj(row["metadata_json"])
    return row


def _skydiscover_ref_path(ref: str) -> PurePosixPath:
    prefix, _sep, rel = ref.partition(":")
    if prefix != "skydiscover" or not rel:
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog refs must use skydiscover:<path>")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref path must stay inside the catalog")
    return pure


def _recognize_skydiscover_target(target: Path) -> str:
    if target.is_file() and target.suffix == ".py":
        return "skydiscover_python_evaluator"
    if not target.is_dir():
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref target is not a supported evaluator or task")
    if (target / "task.toml").is_file() or ((target / "instruction.md").is_file() and (target / "tests").is_dir()):
        return "harbor_task"
    if (target / "Dockerfile").is_file() and (target / "evaluate.sh").is_file():
        return "skydiscover_docker_evaluator"
    python_entry = (target / "evaluator.py").is_file() or (target / "evaluate.py").is_file()
    dependency_manifest = (target / "pyproject.toml").is_file() or (target / "requirements.txt").is_file()
    if python_entry or (dependency_manifest and any(child.suffix == ".py" for child in target.iterdir() if child.is_file())):
        return "skydiscover_python_evaluator"
    raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref target is not a recognized evaluator or task")


def _resolve_skydiscover_catalog_ref(conn, ref: str) -> dict[str, str]:
    rel = _skydiscover_ref_path(ref)
    try:
        catalog = _active_catalog_row(conn)
    except AlabError as exc:
        if exc.code == "CATALOG_NOT_FOUND":
            raise AlabError("CONFIG_INVALID", "active SkyDiscover catalog not found", "alab catalog skydiscover add") from exc
        raise
    catalog_root = Path(catalog["local_path"]).resolve()
    target = (catalog_root / Path(*rel.parts)).resolve()
    if target != catalog_root and catalog_root not in target.parents:
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref path escapes the catalog")
    if not target.exists():
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref target does not exist")
    target_kind = _recognize_skydiscover_target(target)
    return {
        "ref": ref,
        "relative_path": rel.as_posix(),
        "target_kind": target_kind,
        "pinned_commit": catalog["pinned_commit"],
        "target_path": str(target),
    }


def _resolve_local_adapter_ref(ref: str) -> dict[str, str]:
    target = Path(ref).expanduser().resolve()
    if not target.exists():
        raise AlabError("CONFIG_INVALID", "adapter ref target does not exist")
    target_kind = _recognize_skydiscover_target(target)
    return {
        "ref": ref,
        "relative_path": target.name,
        "target_kind": target_kind,
        "pinned_commit": "",
        "target_path": str(target),
    }


def _resolve_harbor_task_ref(conn, ref: str) -> dict[str, str]:
    resolved = _resolve_skydiscover_catalog_ref(conn, ref) if ref.startswith("skydiscover:") else _resolve_local_adapter_ref(ref)
    if resolved["target_kind"] != "harbor_task":
        raise AlabError("CONFIG_INVALID", "runner.harbor_task_ref must resolve to a Harbor-compatible task")
    return resolved


def _resolve_runner_adapter_ref(conn, ref: str) -> dict[str, str]:
    return _resolve_skydiscover_catalog_ref(conn, ref) if ref.startswith("skydiscover:") else _resolve_local_adapter_ref(ref)


def _upsert_catalog(conn, *, origin_url: str, pinned_commit: str, local_path: Path, status: str) -> None:
    metadata = {
        "schema_version": 1,
        "safe_summary": f"SkyDiscover catalog pinned at {pinned_commit[:12]}",
        "task_refs": [],
        "evaluator_refs": [],
        "warnings": [],
    }
    now = utc_now()
    conn.execute(
        """
        INSERT INTO catalogs(catalog_key, catalog_type, origin_url, pinned_commit, local_path,
          status, metadata_json, retrieved_at, updated_at, removed_at)
        VALUES ('skydiscover', 'skydiscover', ?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(catalog_key) DO UPDATE SET
          catalog_type = excluded.catalog_type,
          origin_url = excluded.origin_url,
          pinned_commit = excluded.pinned_commit,
          local_path = excluded.local_path,
          status = excluded.status,
          metadata_json = excluded.metadata_json,
          retrieved_at = excluded.retrieved_at,
          updated_at = excluded.updated_at,
          removed_at = NULL
        """,
        (origin_url, pinned_commit, str(local_path), status, canonical_json(metadata), now, now),
    )


def _clone_or_refresh_catalog(local_path: Path, origin_url: str, *, existing: bool, expected_origin_url: str | None = None) -> None:
    if existing:
        if not (local_path / ".git").exists():
            raise AlabError("CONFIG_INVALID", "catalog local path is not a Git repository")
        current = run_cmd(["git", "remote", "get-url", "origin"], cwd=local_path, check=False)
        if current.returncode != 0:
            raise AlabError("CONFIG_INVALID", "catalog has no origin remote")
        current_url = current.stdout.decode("utf-8", errors="replace").strip()
        if expected_origin_url and current_url != expected_origin_url:
            raise AlabError("CONFIG_INVALID", "catalog has unexpected origin remote")
        if current_url != origin_url:
            _catalog_git(local_path, ["remote", "set-url", "origin", origin_url], "catalog origin update failed")
        dirty = run_cmd(["git", "status", "--porcelain"], cwd=local_path, check=False)
        if dirty.stdout.decode("utf-8", errors="replace").strip():
            raise AlabError("CONFIG_INVALID", "catalog has non-ALab modifications")
        return
    if local_path.exists() and any(local_path.iterdir()):
        raise AlabError("CONFIG_INVALID", "catalog local path already exists")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists():
        local_path.rmdir()
    try:
        run_cmd(["git", "clone", "--quiet", origin_url, str(local_path)])
    except AlabError as exc:
        if exc.code == "GIT_ERROR":
            raise AlabError("CONFIG_INVALID", f"catalog clone failed: {exc.reason}") from exc
        raise


def _catalog_references_skydiscover(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("skydiscover:")
    if isinstance(value, dict):
        return any(_catalog_references_skydiscover(child) for child in value.values())
    if isinstance(value, list):
        return any(_catalog_references_skydiscover(child) for child in value)
    return False


def _skydiscover_remove_blockers(conn) -> list[str]:
    blockers: list[str] = []
    projects = all_rows(conn, "SELECT * FROM projects WHERE status != 'archived'", ())
    for project in projects:
        versions = {
            project["latest_attempted_config_version"],
            project["active_valid_config_version"],
        }
        for version in sorted(v for v in versions if v is not None):
            row = one(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?", (project["project_id"], version))
            if row and _catalog_references_skydiscover(project_config_json_obj(row["canonical_config_json"])):
                blockers.append(f"active_config:{project['project_id']}:{version}")
    open_exps = all_rows(conn, "SELECT project_id, exp_id, bound_config_version FROM experiments WHERE status = 'open'", ())
    for exp in open_exps:
        row = one(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?", (exp["project_id"], exp["bound_config_version"]))
        if row and _catalog_references_skydiscover(project_config_json_obj(row["canonical_config_json"])):
            blockers.append(f"open_experiment:{exp['exp_id']}")
    return blockers


def cmd_catalog_skydiscover_add(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--origin-url", "--ref", "--commit"))
    require_options_at_most_once(args, ("--origin-url", "--ref", "--commit"))
    require_positional_count(args, 0, "catalog skydiscover add accepts no positional arguments")
    origin_url = command_arg(args, "--origin-url", default=SKYDISCOVER_ORIGIN_URL)
    ref = command_arg(args, "--ref")
    raw_commit = command_arg(args, "--commit")
    if ref and raw_commit:
        raise AlabError("CONFIG_INVALID", "--ref conflicts with --commit")
    commit = _full_commit_sha_filter(raw_commit)
    db = Database(req.globals.home)
    db.migrate()
    local_path = _catalog_local_path(req.globals.home)
    with db.tx() as conn:
        if one(conn, "SELECT 1 FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'"):
            raise AlabError("CONFIG_INVALID", "active SkyDiscover catalog already exists")
    _clone_or_refresh_catalog(local_path, origin_url, existing=False)
    pinned_commit, requested = _resolve_catalog_commit(local_path, ref=ref, commit=commit)
    _catalog_git(local_path, ["checkout", "--quiet", pinned_commit], "catalog checkout failed")
    with db.tx() as conn:
        _upsert_catalog(conn, origin_url=origin_url, pinned_commit=pinned_commit, local_path=local_path, status="active")
        audit_id = audit(conn, action="add", object_type="catalog", object_id="skydiscover", actor=actor, metadata={"schema_version": 1, "requested_ref": requested, "pinned_commit": pinned_commit})
        row = _active_catalog_row(conn)
    return [
        ResultBlock(
            "catalog",
            [
                ("catalog", "skydiscover"),
                ("origin url", origin_url),
                ("requested ref", requested),
                ("pinned commit", pinned_commit),
                ("local path", str(local_path)),
                ("retrieved at", row["retrieved_at"]),
                ("status", "active"),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_catalog_skydiscover_update(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--origin-url", "--ref", "--commit"))
    require_options_at_most_once(args, ("--origin-url", "--ref", "--commit"))
    require_positional_count(args, 0, "catalog skydiscover update accepts no positional arguments")
    ref = command_arg(args, "--ref")
    raw_commit = command_arg(args, "--commit")
    if ref and raw_commit:
        raise AlabError("CONFIG_INVALID", "--ref conflicts with --commit")
    commit = _full_commit_sha_filter(raw_commit)
    with Database(req.globals.home).tx() as conn:
        row = _active_catalog_row(conn)
        origin_url = command_arg(args, "--origin-url", default=row["origin_url"])
        local_path = Path(row["local_path"])
    _clone_or_refresh_catalog(local_path, origin_url, existing=True, expected_origin_url=row["origin_url"])
    pinned_commit, requested = _resolve_catalog_commit(local_path, ref=ref, commit=commit)
    _catalog_git(local_path, ["checkout", "--quiet", pinned_commit], "catalog checkout failed")
    with Database(req.globals.home).tx() as conn:
        _upsert_catalog(conn, origin_url=origin_url, pinned_commit=pinned_commit, local_path=local_path, status="active")
        audit_id = audit(conn, action="update", object_type="catalog", object_id="skydiscover", actor=actor, metadata={"schema_version": 1, "requested_ref": requested, "pinned_commit": pinned_commit})
        row = _active_catalog_row(conn)
    return [
        ResultBlock(
            "catalog",
            [
                ("catalog", "skydiscover"),
                ("origin url", origin_url),
                ("requested ref", requested),
                ("pinned commit", pinned_commit),
                ("local path", str(local_path)),
                ("retrieved at", row["retrieved_at"]),
                ("status", "active"),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_catalog_skydiscover_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_actor(req, "root")
    require_known_options(args, ())
    require_positional_count(args, 0, "catalog skydiscover show accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        row = _active_catalog_row(conn)
        return [
            ResultBlock(
                "catalog",
                [
                    ("catalog", "skydiscover"),
                    ("origin url", row["origin_url"]),
                    ("pinned commit", row["pinned_commit"]),
                    ("local path", row["local_path"]),
                    ("retrieved at", row["retrieved_at"]),
                    ("status", row["status"]),
                ],
            )
        ]
    finally:
        conn.close()


def cmd_catalog_skydiscover_remove(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--force", "--confirm", "--reason"))
    require_force_confirm(args, "skydiscover", "catalog remove requires --force and --confirm skydiscover")
    require_positional_count(args, 0, "catalog skydiscover remove accepts no positional arguments")
    reason = _lifecycle_reason(args)
    with Database(req.globals.home).tx() as conn:
        row = _active_catalog_row(conn)
        blockers = _skydiscover_remove_blockers(conn)
        if blockers:
            raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
        local_path = Path(row["local_path"])
        if local_path.exists():
            resolved = local_path.resolve()
            allowed = req.globals.home.sources_path.resolve()
            if resolved != allowed and allowed not in resolved.parents:
                raise AlabError("CONFIG_INVALID", "catalog local path escapes ALAB_HOME sources")
            shutil.rmtree(local_path)
        now = utc_now()
        conn.execute("UPDATE catalogs SET status = 'removed', removed_at = ?, updated_at = ? WHERE catalog_key = 'skydiscover'", (now, now))
        audit_id = audit(conn, action="remove", object_type="catalog", object_id="skydiscover", actor=actor, reason=reason, metadata={"schema_version": 1})
    return [ResultBlock("catalog", [("catalog", "skydiscover"), ("removed", True), ("audit id", audit_id)])]
