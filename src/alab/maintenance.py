from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .db import Database, all_rows
from .errors import AlabError
from .removal import _remove_path_if_safe, _remove_trash_cache_path
from .rendering import ResultBlock
from .runner import prune_docker_image
from .service_args import (
    command_arg,
    flag,
    require_exactly_one_option_pair,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_audit import audit
from .service_auth import require_actor
from .service_models import Request
from .timeutil import utc_now


def _parse_days(args: list[str], name: str) -> int | None:
    value = command_arg(args, name)
    if value is None:
        return None
    try:
        days = int(value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be an integer number of days") from exc
    if days < 0:
        raise AlabError("CONFIG_INVALID", f"{name} must be zero or greater")
    return days


def _parse_backup_keep(args: list[str]) -> int | None:
    keep_value = command_arg(args, "--keep")
    if keep_value is None:
        return None
    try:
        keep = int(keep_value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "--keep must be an integer") from exc
    if keep < 0:
        raise AlabError("CONFIG_INVALID", "--keep must be zero or greater")
    return keep


def cmd_backup_prune(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--keep", "--older-than"))
    require_exactly_one_option_pair(args, "--keep", "--older-than", "backup prune requires exactly one of --keep or --older-than")
    require_positional_count(args, 0, "backup prune accepts no positional arguments")
    keep = _parse_backup_keep(args)
    older_than = _parse_days(args, "--older-than")
    backups = sorted(req.globals.home.backups_path.glob("*.db"), key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    if keep is not None:
        prune = backups[keep:]
    else:
        threshold = datetime.now(UTC) - timedelta(days=older_than or 0)
        prune = [path for path in backups if datetime.fromtimestamp(path.stat().st_mtime, UTC) < threshold]
    pruned: list[str] = []
    for path in prune:
        _remove_path_if_safe(path, req.globals.home.path)
        pruned.append(str(path))
    with Database(req.globals.home).tx() as conn:
        audit_id = audit(
            conn,
            action="prune",
            object_type="backup",
            object_id="backups",
            actor=actor,
            metadata={"schema_version": 1, "pruned_count": len(pruned)},
        )
    return [ResultBlock("backup_prune", [("backup pruned count", len(pruned)), ("backup path", pruned), ("audit id", audit_id)])]


def _cache_cutoff(args: list[str]) -> str | None:
    days = _parse_days(args, "--older-than")
    if days is None:
        return None
    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cmd_cache_prune(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--all", "--docker-images", "--skydiscover-envs", "--trash", "--trash-all", "--older-than"))
    require_options_at_most_once(args, ("--all", "--docker-images", "--skydiscover-envs", "--trash", "--trash-all", "--older-than"))
    all_flag = flag(args, "--all")
    explicit_selectors = [flag(args, "--docker-images"), flag(args, "--skydiscover-envs"), flag(args, "--trash"), flag(args, "--trash-all")]
    if all_flag and any(explicit_selectors):
        raise AlabError("CONFIG_INVALID", "--all conflicts with specific cache selectors")
    if all_flag and command_arg(args, "--older-than") is not None:
        raise AlabError("CONFIG_INVALID", "--all conflicts with --older-than")
    if not all_flag and not any(explicit_selectors):
        raise AlabError("CONFIG_INVALID", "cache prune requires at least one selector")
    if flag(args, "--trash") and flag(args, "--trash-all"):
        raise AlabError("CONFIG_INVALID", "--trash conflicts with --trash-all")
    if flag(args, "--trash-all") and command_arg(args, "--older-than") is not None:
        raise AlabError("CONFIG_INVALID", "--trash-all conflicts with --older-than")
    if flag(args, "--trash") and command_arg(args, "--older-than") is None:
        raise AlabError("CONFIG_INVALID", "--trash requires --older-than")
    if not flag(args, "--trash") and command_arg(args, "--older-than") is not None and not all_flag:
        raise AlabError("CONFIG_INVALID", "--older-than is only valid with --trash")
    require_positional_count(args, 0, "cache prune accepts no positional arguments")
    kinds: set[str] = set()
    if all_flag or flag(args, "--docker-images"):
        kinds.add("docker_image")
    if all_flag or flag(args, "--skydiscover-envs"):
        kinds.add("skydiscover_python_env")
    if all_flag or flag(args, "--trash") or flag(args, "--trash-all"):
        kinds.add("trash")
    cutoff = None if all_flag or flag(args, "--trash-all") else _cache_cutoff(args)
    warnings: list[tuple[str, str]] = []
    with Database(req.globals.home).tx() as conn:
        clauses = ["status = 'active'"]
        params: list[Any] = []
        placeholders = ", ".join("?" for _ in kinds)
        clauses.append(f"cache_kind IN ({placeholders})")
        params.extend(sorted(kinds))
        if cutoff:
            clauses.append("(cache_kind != 'trash' OR COALESCE(last_used_at, created_at) < ?)")
            params.append(cutoff)
        rows = all_rows(conn, f"SELECT * FROM cache_entries WHERE {' AND '.join(clauses)} ORDER BY cache_kind, cache_key", tuple(params))
        pruned_count = 0
        for row in rows:
            if row["cache_kind"] == "docker_image" and row["docker_tag"]:
                removed, reason = prune_docker_image(row["docker_tag"])
                if not removed:
                    warnings.append(("DOCKER_CACHE_PRUNE_FAILED", f"{row['docker_tag']}: {reason}"))
                    continue
            if row["path"]:
                if row["cache_kind"] == "trash":
                    _remove_trash_cache_path(Path(row["path"]), req.globals.home)
                else:
                    _remove_path_if_safe(Path(row["path"]), req.globals.home.path)
            conn.execute("UPDATE cache_entries SET status = 'removed', removed_at = ? WHERE cache_id = ?", (utc_now(), row["cache_id"]))
            pruned_count += 1
        audit_id = audit(
            conn,
            action="prune",
            object_type="cache",
            object_id="cache",
            actor=actor,
            metadata={"schema_version": 1, "cache_kinds": sorted(kinds), "pruned_count": pruned_count, "warning_count": len(warnings)},
        )
    blocks = [
        ResultBlock(
            "cache_prune",
            [
                ("cache pruned count", pruned_count),
                ("cache kind", sorted(kinds)),
                ("audit id", audit_id),
            ],
        )
    ]
    for code, reason in warnings:
        blocks.append(ResultBlock("warning", [("warning code", code), ("warning reason", reason)]))
    return blocks
