from __future__ import annotations

import json
import sqlite3
from typing import Any

from .errors import AlabError
from .timeutil import parse_rfc3339_utc

OPTIONS_WITH_VALUES = {
    "--home",
    "--output",
    "--key",
    "--role",
    "--config",
    "--project",
    "--source-path",
    "--source-git",
    "--source-ref",
    "--from-exp",
    "--from-commit",
    "--git-ref",
    "--source-subdir",
    "--mutable-include",
    "--mutable-exclude",
    "--visibility-scope",
    "--visible-exp",
    "--name",
    "--task",
    "--goal",
    "--path",
    "--message",
    "--summary",
    "--summary-file",
    "--feedback",
    "--feedback-file",
    "--ref",
    "--out",
    "--version",
    "--confirm",
    "--reason",
    "--body",
    "--body-file",
    "--kind",
    "--title",
    "--target",
    "--tag",
    "--limit",
    "--offset",
    "--query",
    "--run",
    "--exp",
    "--validation",
    "--object-type",
    "--object-id",
    "--action",
    "--actor",
    "--created-after",
    "--created-before",
    "--updated-after",
    "--updated-before",
    "--started-after",
    "--started-before",
    "--ended-after",
    "--ended-before",
    "--max-files",
    "--max-total-bytes",
    "--max-file-bytes",
    "--status",
    "--source-id",
    "--name-query",
    "--reward-min",
    "--reward-max",
    "--runner-type",
    "--exit-code",
    "--failure-reason-query",
    "--content-hash",
    "--path-query",
    "--root",
    "--stream",
    "--sort",
    "--config-version",
    "--token-id",
    "--mode",
    "--size-min",
    "--size-max",
    "--truncated",
    "--value-file",
    "--commit",
    "--private-to-exp",
    "--author",
    "--target-type",
    "--target-id",
    "--created-by",
    "--keep",
    "--older-than",
    "--origin-url",
    "--port",
    "--refresh-seconds",
}


EMPTY_COMMAND_VALUE_ALLOWED = {
    "--author",
    "--body",
    "--failure-reason-query",
    "--feedback",
    "--goal",
    "--message",
    "--name-query",
    "--path-query",
    "--query",
    "--reason",
    "--summary",
}


def _command_value(name: str, value: str) -> str:
    if value == "" and name not in EMPTY_COMMAND_VALUE_ALLOWED:
        raise AlabError("CONFIG_INVALID", f"{name} requires a non-empty value")
    return value


def command_arg(args: list[str], name: str, *, required: bool = False, default: str | None = None) -> str | None:
    if name in args:
        idx = args.index(name)
        if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
            raise AlabError("CONFIG_INVALID", f"{name} requires a value")
        return _command_value(name, args[idx + 1])
    if required:
        raise AlabError("CONFIG_INVALID", f"missing required option {name}")
    return default


def command_args(args: list[str], name: str) -> list[str]:
    values: list[str] = []
    for idx, item in enumerate(args):
        if item == name:
            if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
                raise AlabError("CONFIG_INVALID", f"{name} requires a value")
            values.append(_command_value(name, args[idx + 1]))
    return values


def option_count(args: list[str], name: str) -> int:
    return sum(1 for item in args if item == name)


def require_options_at_most_once(args: list[str], options: tuple[str, ...]) -> None:
    for option in options:
        if option_count(args, option) > 1:
            raise AlabError("CONFIG_INVALID", f"{option} may be provided once")


def require_known_options(args: list[str], allowed_options: tuple[str, ...]) -> None:
    allowed = set(allowed_options)
    for item in args:
        if item == "--":
            break
        if item.startswith("--") and item not in allowed:
            raise AlabError("CONFIG_INVALID", f"unsupported option {item}")


def require_exactly_one_option_pair(args: list[str], first: str, second: str, message: str) -> None:
    require_options_at_most_once(args, (first, second))
    if option_count(args, first) + option_count(args, second) != 1:
        raise AlabError("CONFIG_INVALID", message)


def require_force_confirm(args: list[str], expected_confirm: str, message: str) -> None:
    require_options_at_most_once(args, ("--force", "--confirm"))
    if option_count(args, "--force") != 1 or option_count(args, "--confirm") != 1 or command_arg(args, "--confirm") != expected_confirm:
        raise AlabError("CONFIG_INVALID", message)


def require_dry_run_unforced(args: list[str]) -> None:
    require_options_at_most_once(args, ("--force", "--confirm"))
    if flag(args, "--dry-run") and (flag(args, "--force") or option_count(args, "--confirm")):
        raise AlabError("CONFIG_INVALID", "--dry-run conflicts with --force/--confirm")


def require_dry_run_skip_baseline_compatible(args: list[str]) -> None:
    if flag(args, "--dry-run") and flag(args, "--skip-baseline-test"):
        raise AlabError("CONFIG_INVALID", "--dry-run conflicts with --skip-baseline-test")


def require_positional_count(args: list[str], count: int, message: str, *, options_with_values: tuple[str, ...] | None = None) -> list[str]:
    pos = positional(args, options_with_values=options_with_values)
    if len(pos) != count:
        raise AlabError("CONFIG_INVALID", message)
    return pos


def optional_positional_selector(args: list[str], message: str, *, options_with_values: tuple[str, ...] | None = None) -> str | None:
    pos = positional(args, options_with_values=options_with_values)
    if len(pos) > 1:
        raise AlabError("CONFIG_INVALID", message)
    return pos[0] if pos else None


def flag(args: list[str], name: str) -> bool:
    return name in args


def positional(args: list[str], *, options_with_values: tuple[str, ...] | None = None) -> list[str]:
    result: list[str] = []
    skip = False
    value_options = OPTIONS_WITH_VALUES if options_with_values is None else set(options_with_values)
    for idx, item in enumerate(args):
        if skip:
            skip = False
            continue
        if item in value_options:
            if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
                raise AlabError("CONFIG_INVALID", f"{item} requires a value")
            _command_value(item, args[idx + 1])
            skip = True
            continue
        if item.startswith("--"):
            continue
        result.append(item)
    return result


def _parse_limit_offset(args: list[str]) -> tuple[int, int]:
    require_options_at_most_once(args, ("--limit", "--offset"))
    try:
        limit = int(command_arg(args, "--limit", default="50") or "50")
        offset = int(command_arg(args, "--offset", default="0") or "0")
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "--limit and --offset must be integers") from exc
    if limit < 1 or limit > 500:
        raise AlabError("CONFIG_INVALID", "--limit must be between 1 and 500")
    if offset < 0:
        raise AlabError("CONFIG_INVALID", "--offset must be zero or greater")
    return limit, offset


def _parse_audit_limit_offset(args: list[str]) -> tuple[int, int]:
    require_options_at_most_once(args, ("--limit", "--offset"))
    try:
        limit = int(command_arg(args, "--limit", default="50") or "50")
        offset = int(command_arg(args, "--offset", default="0") or "0")
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "--limit and --offset must be integers") from exc
    if limit < 1 or limit > 1000:
        raise AlabError("CONFIG_INVALID", "invalid audit pagination")
    if offset < 0:
        raise AlabError("CONFIG_INVALID", "invalid audit pagination")
    return limit, offset


def _parse_float_option(args: list[str], name: str) -> float | None:
    require_options_at_most_once(args, (name,))
    value = command_arg(args, name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be numeric") from exc


def _parse_int_option(args: list[str], name: str) -> int | None:
    require_options_at_most_once(args, (name,))
    value = command_arg(args, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be an integer") from exc


def _parse_non_negative_int_option(args: list[str], name: str) -> int | None:
    value = _parse_int_option(args, name)
    if value is not None and value < 0:
        raise AlabError("CONFIG_INVALID", f"{name} must be zero or greater")
    return value


def _parse_positive_int_option(args: list[str], name: str) -> int | None:
    value = _parse_int_option(args, name)
    if value is not None and value < 1:
        raise AlabError("CONFIG_INVALID", f"{name} must be a positive integer")
    return value


def _require_ordered_range(
    min_value: int | float | None,
    max_value: int | float | None,
    min_name: str,
    max_name: str,
) -> None:
    if min_value is not None and max_value is not None and min_value > max_value:
        raise AlabError("CONFIG_INVALID", f"{min_name} must be less than or equal to {max_name}")


def _require_option_choice(value: str | None, name: str, choices: set[str]) -> str | None:
    if value is None:
        return None
    if value not in choices:
        raise AlabError("CONFIG_INVALID", f"{name} must be one of {', '.join(sorted(choices))}")
    return value


def _is_commit_sha_selector(selector: str) -> bool:
    return 4 <= len(selector) <= 40 and all(char in "0123456789abcdefABCDEF" for char in selector)


def _commit_sha_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if not _is_commit_sha_selector(value):
        raise AlabError("CONFIG_INVALID", "--commit must be a commit SHA")
    return value.lower()


def _exp_commit_selector_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if value in {"latest", "final", "best"}:
        return value
    if not _is_commit_sha_selector(value):
        raise AlabError("CONFIG_INVALID", "commit selector must be latest, final, best, or a commit SHA")
    return value.lower()


def _full_commit_sha_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) != 40 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise AlabError("CONFIG_INVALID", "--commit requires a full commit SHA")
    return value.lower()


def _content_hash_filter(value: str | None) -> str | None:
    if value is None:
        return None
    prefix = "sha256:"
    digest = value.removeprefix(prefix)
    if not value.startswith(prefix) or len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
        raise AlabError("CONFIG_INVALID", "--content-hash must be sha256:<64-hex>")
    return prefix + digest.lower()


def _parse_bool_option(args: list[str], name: str) -> bool | None:
    require_options_at_most_once(args, (name,))
    value = command_arg(args, name)
    if value is None:
        return None
    if value.lower() in {"true", "1", "yes"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise AlabError("CONFIG_INVALID", f"{name} must be true or false")


def _append_time_filter(args: list[str], clauses: list[str], params: list[Any], option: str, column: str, op: str) -> None:
    require_options_at_most_once(args, (option,))
    value = command_arg(args, option)
    if value:
        clauses.append(f"{column} {op} ?")
        params.append(parse_rfc3339_utc(value))


def _require_ordered_time_range(args: list[str], after_option: str, before_option: str) -> None:
    require_options_at_most_once(args, (after_option, before_option))
    after_value = command_arg(args, after_option)
    before_value = command_arg(args, before_option)
    if after_value and before_value and parse_rfc3339_utc(after_value) > parse_rfc3339_utc(before_value):
        raise AlabError("CONFIG_INVALID", f"{after_option} must be less than or equal to {before_option}")


def _paginate_rows(args: list[str], rows: list[Any]) -> list[Any]:
    limit, offset = _parse_limit_offset(args)
    return rows[offset : offset + limit]


def _sort_rows(
    args: list[str],
    rows: list[Any],
    *,
    default: str,
    allowed: dict[str, Any],
    subject: str,
) -> list[Any]:
    require_options_at_most_once(args, ("--sort",))
    sort_text = command_arg(args, "--sort", default=default) or default
    field, sep, direction = sort_text.partition(":")
    if not field:
        raise AlabError("CONFIG_INVALID", "--sort field is required")
    if not sep:
        direction = "desc"
    if direction not in {"asc", "desc"}:
        raise AlabError("CONFIG_INVALID", "--sort direction must be asc or desc")
    if field not in allowed:
        raise AlabError("CONFIG_INVALID", f"--sort field is not supported for {subject}")
    nulls: list[Any] = []
    values: list[tuple[Any, Any]] = []
    for row in rows:
        value = allowed[field](row)
        if value is None:
            nulls.append(row)
            continue
        if isinstance(value, str):
            value = value.casefold()
        elif isinstance(value, bool):
            value = int(value)
        values.append((value, row))
    values.sort(key=lambda item: item[0], reverse=direction == "desc")
    return [row for _value, row in values] + nulls


def _sql_casefold_contains(value: Any, query: Any) -> int:
    return int(str(query).casefold() in str(value or "").casefold())


def _sql_casefold(value: Any) -> str:
    return str(value or "").casefold()


def _sql_record_json_field_casefold_contains(record_json: Any, field: Any, query: Any) -> int:
    try:
        record = json.loads(str(record_json))
    except (TypeError, json.JSONDecodeError):
        return 0
    if not isinstance(record, dict):
        return 0
    return _sql_casefold_contains(record.get(str(field)), query)


def _register_observe_text_predicates(conn: sqlite3.Connection) -> None:
    conn.create_function("alab_casefold", 1, _sql_casefold)
    conn.create_function("alab_casefold_contains", 2, _sql_casefold_contains)
    conn.create_function("alab_record_json_field_casefold_contains", 3, _sql_record_json_field_casefold_contains)


def _sql_order_limit_clause(
    args: list[str],
    *,
    default: str,
    allowed: dict[str, str],
    subject: str,
    tie_breakers: tuple[str, ...] = (),
) -> tuple[str, tuple[Any, ...]]:
    require_options_at_most_once(args, ("--sort",))
    sort_text = command_arg(args, "--sort", default=default) or default
    field, sep, direction = sort_text.partition(":")
    if not field:
        raise AlabError("CONFIG_INVALID", "--sort field is required")
    if not sep:
        direction = "desc"
    if direction not in {"asc", "desc"}:
        raise AlabError("CONFIG_INVALID", "--sort direction must be asc or desc")
    if field not in allowed:
        raise AlabError("CONFIG_INVALID", f"--sort field is not supported for {subject}")
    limit, offset = _parse_limit_offset(args)
    expression = allowed[field]
    terms = [f"{expression} IS NULL ASC", f"{expression} {direction.upper()}", *tie_breakers]
    return f"ORDER BY {', '.join(terms)} LIMIT ? OFFSET ?", (limit, offset)
