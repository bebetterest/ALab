from __future__ import annotations

from typing import Any

from . import services as _core
from .auth import Actor
from .configs import project_config_json_obj
from .db import all_rows, canonical_json, one
from .errors import AlabError
from .rendering import ResultBlock
from .service_args import (
    _parse_float_option,
    _parse_limit_offset,
    _parse_positive_int_option,
    _register_observe_text_predicates,
    _require_option_choice,
    _require_ordered_range,
    _require_ordered_time_range,
    _sql_order_limit_clause,
    command_arg,
    command_args,
    flag,
    optional_positional_selector,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_home
from .service_contracts import experiment_metadata_obj, experiment_policy_json_obj
from .service_models import EXPERIMENT_STATUSES, Request
from .timeutil import parse_rfc3339_utc

_project_row = _core._project_row
_project_id_from_request = _core._project_id_from_request
_complete_id_option = _core._complete_id_option
_complete_id_or_missing = _core._complete_id_or_missing
_exp_row = _core._exp_row
_authorize_observe = _core._authorize_observe
_tag_slug = _core._tag_slug
_tag_values = _core._tag_values


def _reward_identity_from_config_json(config_json: dict[str, Any]) -> str:
    reward = config_json.get("reward") or {}
    comparable = {
        "schema_version": 1,
        "type": reward.get("type"),
        "direction": reward.get("direction", "maximize"),
        "primary_metric": reward.get("primary_metric", "reward"),
        "path": reward.get("path"),
        "pattern": reward.get("pattern"),
    }
    return canonical_json(comparable)


def _reward_direction_from_config_json(config_json: dict[str, Any]) -> str:
    reward = config_json.get("reward") or {}
    direction = reward.get("direction", "maximize")
    if direction not in {"maximize", "minimize"}:
        raise AlabError("CONFIG_INVALID", "invalid reward direction in config")
    return direction


def _config_json_for_version(conn, project_id: str, version: int) -> dict[str, Any]:
    row = one(
        conn,
        "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
        (project_id, version),
    )
    if row is None:
        raise AlabError("CONFIG_INVALID", "config version not found")
    return project_config_json_obj(row["canonical_config_json"])


def _current_visibility_policy(conn, project: Any) -> dict[str, Any]:
    version = project["latest_attempted_config_version"] or project["active_valid_config_version"]
    if not version:
        return {"scope": "none", "experiment_ids": []}
    config_json = _config_json_for_version(conn, project["project_id"], int(version))
    return config_json.get("visibility") or {"scope": "none", "experiment_ids": []}


def _intersect_visibility(
    current: dict[str, Any], upper_bound: dict[str, Any]
) -> tuple[str, set[str]]:
    current_scope = current.get("scope", "none")
    upper_scope = upper_bound.get("scope", "none")
    if "none" in {current_scope, upper_scope}:
        return "none", set()
    if current_scope == "same_project" and upper_scope == "same_project":
        return "same_project", set()
    if current_scope == "explicit" and upper_scope == "explicit":
        return "explicit", set(current.get("experiment_ids") or []) & set(
            upper_bound.get("experiment_ids") or []
        )
    if current_scope == "explicit":
        return "explicit", set(current.get("experiment_ids") or [])
    if upper_scope == "explicit":
        return "explicit", set(upper_bound.get("experiment_ids") or [])
    return "none", set()


def _public_from_exp_visible(conn, project: Any, source_exp: Any) -> bool:
    if source_exp["status"] not in {"open", "closed"}:
        return False
    upper_bound = experiment_policy_json_obj(source_exp["policy_json"]).get(
        "visibility_upper_bound"
    ) or {"scope": "none", "experiment_ids": []}
    scope, explicit_ids = _intersect_visibility(
        _current_visibility_policy(conn, project), upper_bound
    )
    if scope == "same_project":
        return True
    if scope == "explicit":
        return source_exp["exp_id"] in explicit_ids
    return False


def _visible_exp_ids(conn, project_id: str, actor: Actor) -> set[str] | None:
    if actor.actor_type in {"root", "admin"}:
        return None
    if not actor.exp_id:
        return set()
    project = _project_row(conn, project_id)
    source_exp = _exp_row(conn, project_id, actor.exp_id)
    policy = experiment_policy_json_obj(source_exp["policy_json"]).get(
        "visibility_upper_bound"
    ) or {"scope": "none", "experiment_ids": []}
    scope, explicit_ids = _intersect_visibility(_current_visibility_policy(conn, project), policy)
    visible = {actor.exp_id}
    if scope == "same_project":
        visible.update(
            row["exp_id"]
            for row in all_rows(
                conn, "SELECT exp_id FROM experiments WHERE project_id = ?", (project_id,)
            )
        )
    elif scope == "explicit":
        visible.update(explicit_ids)
    return visible


def _append_visible_exp_clause(
    conn,
    project_id: str,
    actor: Actor,
    clauses: list[str],
    params: list[Any],
    *,
    column: str = "exp_id",
) -> None:
    if actor.actor_type in {"root", "admin"}:
        return
    if not actor.exp_id:
        clauses.append("1 = 0")
        return
    project = _project_row(conn, project_id)
    source_exp = _exp_row(conn, project_id, actor.exp_id)
    policy = experiment_policy_json_obj(source_exp["policy_json"]).get(
        "visibility_upper_bound"
    ) or {"scope": "none", "experiment_ids": []}
    scope, explicit_ids = _intersect_visibility(_current_visibility_policy(conn, project), policy)
    if scope == "same_project":
        clauses.append(f"{column} IS NOT NULL")
        return
    visible = {actor.exp_id}
    if scope == "explicit":
        visible.update(explicit_ids)
    visible_clause, visible_params = _sql_in_clause(column, visible)
    clauses.append(visible_clause)
    params.extend(visible_params)


def _exp_visible(conn, project_id: str, actor: Actor, exp_id: str | None) -> bool:
    if actor.actor_type in {"root", "admin"}:
        return True
    if not exp_id:
        return False
    visible = _visible_exp_ids(conn, project_id, actor)
    return exp_id in (visible or set())


def _best_context(conn, project: Any, args: list[str]) -> tuple[int | None, str | None, str]:
    explicit_version = _parse_positive_int_option(args, "--config-version")
    if explicit_version is not None:
        config_json = _config_json_for_version(conn, project["project_id"], explicit_version)
        return explicit_version, None, _reward_direction_from_config_json(config_json)
    active = project["active_valid_config_version"]
    if active is None:
        raise AlabError(
            "PROJECT_INVALID", "best requires an active valid config or explicit --config-version"
        )
    config_json = _config_json_for_version(conn, project["project_id"], int(active))
    return (
        None,
        _reward_identity_from_config_json(config_json),
        _reward_direction_from_config_json(config_json),
    )


def _optional_best_context(conn, project: Any) -> tuple[str | None, str]:
    active = project["active_valid_config_version"]
    if active is None:
        return None, "maximize"
    config_json = _config_json_for_version(conn, project["project_id"], int(active))
    return _reward_identity_from_config_json(config_json), _reward_direction_from_config_json(
        config_json
    )


def _best_run_for_experiment(
    conn,
    *,
    project_id: str,
    exp_id: str,
    direction: str,
    config_version: int | None = None,
    reward_identity: str | None = None,
    include_archived_runs: bool = False,
) -> tuple[Any | None, int]:
    clauses = [
        "project_id = ?",
        "exp_id = ?",
        "status = 'passed'",
        "reward_parse_status = 'parsed'",
        "reward_value IS NOT NULL",
    ]
    params: list[Any] = [project_id, exp_id]
    if config_version is not None:
        clauses.append("config_version = ?")
        params.append(config_version)
    if not include_archived_runs:
        clauses.append("archive_status = 'active'")
    rows = all_rows(conn, f"SELECT * FROM runs WHERE {' AND '.join(clauses)}", tuple(params))
    identity_cache: dict[int, str] = {}
    comparable: list[Any] = []
    excluded = 0
    for row in rows:
        if reward_identity is not None:
            version = int(row["config_version"])
            if version not in identity_cache:
                identity_cache[version] = _reward_identity_from_config_json(
                    _config_json_for_version(conn, project_id, version)
                )
            if identity_cache[version] != reward_identity:
                excluded += 1
                continue
        comparable.append(row)
    comparable.sort(key=lambda row: row["exp_id"])
    comparable.sort(key=lambda row: row["ended_at"] or "", reverse=True)
    comparable.sort(key=lambda row: float(row["reward_value"]), reverse=direction == "maximize")
    return (comparable[0] if comparable else None), excluded


def _sql_in_clause(column: str, values: list[Any] | set[Any]) -> tuple[str, tuple[Any, ...]]:
    ordered = sorted(values)
    if not ordered:
        return "1 = 0", ()
    clauses: list[str] = []
    params: list[Any] = []
    for idx in range(0, len(ordered), 900):
        chunk = ordered[idx : idx + 900]
        placeholders = ", ".join("?" for _ in chunk)
        clauses.append(f"{column} IN ({placeholders})")
        params.extend(chunk)
    return f"({' OR '.join(clauses)})", tuple(params)


def _reward_identity_config_versions(
    conn, project_id: str, reward_identity: str | None
) -> list[int] | None:
    if reward_identity is None:
        return None
    versions: list[int] = []
    for row in all_rows(
        conn,
        "SELECT version, canonical_config_json FROM project_config_versions WHERE project_id = ?",
        (project_id,),
    ):
        config_json = project_config_json_obj(row["canonical_config_json"])
        if _reward_identity_from_config_json(config_json) == reward_identity:
            versions.append(int(row["version"]))
    return versions


def _best_run_window_order(direction: str, run_alias: str = "r") -> str:
    reward_direction = "DESC" if direction == "maximize" else "ASC"
    return f"{run_alias}.reward_value {reward_direction}, {run_alias}.ended_at DESC, {run_alias}.exp_id ASC, {run_alias}.rowid ASC"


def _best_run_sql_clauses(
    *,
    project_id: str,
    config_version: int | None,
    reward_config_versions: list[int] | None,
    include_archived_runs: bool,
    exp_ids: list[str] | None = None,
    run_alias: str = "r",
) -> tuple[list[str], list[Any]]:
    prefix = f"{run_alias}."
    clauses = [
        f"{prefix}project_id = ?",
        f"{prefix}status = 'passed'",
        f"{prefix}reward_parse_status = 'parsed'",
        f"{prefix}reward_value IS NOT NULL",
    ]
    params: list[Any] = [project_id]
    if exp_ids is not None:
        exp_clause, exp_params = _sql_in_clause(f"{prefix}exp_id", exp_ids)
        clauses.append(exp_clause)
        params.extend(exp_params)
    if config_version is not None:
        clauses.append(f"{prefix}config_version = ?")
        params.append(config_version)
    elif reward_config_versions is not None:
        version_clause, version_params = _sql_in_clause(
            f"{prefix}config_version", reward_config_versions
        )
        clauses.append(version_clause)
        params.extend(version_params)
    if not include_archived_runs:
        clauses.append(f"{prefix}archive_status = 'active'")
    return clauses, params


def _append_experiment_search_clause(
    conn, clauses: list[str], params: list[Any], exp_alias: str, actor: Actor, query: str
) -> None:
    _register_observe_text_predicates(conn)
    prefix = f"{exp_alias}."
    search_clauses = [
        f"alab_record_json_field_casefold_contains({prefix}metadata_json, 'name', ?) = 1",
        f"alab_record_json_field_casefold_contains({prefix}metadata_json, 'goal', ?) = 1",
        f"""
        EXISTS (
          SELECT 1 FROM project_config_versions pcv
          WHERE pcv.project_id = {prefix}project_id
            AND pcv.version = {prefix}bound_config_version
            AND (
              alab_casefold_contains(json_extract(pcv.canonical_config_json, '$.project.name'), ?) = 1
              OR alab_casefold_contains(json_extract(pcv.canonical_config_json, '$.project.task'), ?) = 1
              OR alab_casefold_contains(json_extract(pcv.canonical_config_json, '$.project.goal'), ?) = 1
            )
        )
        """,
        f"""
        EXISTS (
          SELECT 1 FROM experiment_tags et
          WHERE et.project_id = {prefix}project_id
            AND et.exp_id = {prefix}exp_id
            AND alab_casefold_contains(et.tag_slug, ?) = 1
        )
        """,
        f"""
        EXISTS (
          SELECT 1 FROM experiment_submissions es
          WHERE es.project_id = {prefix}project_id
            AND es.exp_id = {prefix}exp_id
            AND (
              alab_casefold_contains(es.summary, ?) = 1
              OR alab_casefold_contains(es.feedback, ?) = 1
            )
        )
        """,
    ]
    params.extend([query, query, query, query, query, query, query, query])
    if actor.actor_type in {"root", "admin"}:
        annotation_visibility_sql = "1 = 1"
        annotation_params: list[Any] = []
    else:
        annotation_visibility_sql = """
        (
          json_extract(a.visibility_json, '$.scope') = 'project'
          OR (
            json_extract(a.visibility_json, '$.scope') = 'private'
            AND json_extract(a.visibility_json, '$.creator_exp_id') = ?
          )
        )
        """
        annotation_params = [actor.exp_id]
    search_clauses.append(
        f"""
        EXISTS (
          SELECT 1
          FROM annotations a
          JOIN annotation_revisions ar
            ON ar.annotation_id = a.annotation_id
           AND ar.revision = a.current_revision
          WHERE a.project_id = {prefix}project_id
            AND a.status = 'active'
            AND (a.target_id = {prefix}exp_id OR json_extract(a.target_json, '$.exp_id') = {prefix}exp_id)
            AND {annotation_visibility_sql}
            AND alab_casefold_contains(ar.body, ?) = 1
        )
        """
    )
    params.extend(annotation_params)
    params.append(query)
    clauses.append(f"({' OR '.join(search_clauses)})")


def _experiment_query_clauses(
    conn,
    project_id: str,
    actor: Actor,
    args: list[str],
    *,
    table_alias: str = "e",
    search_query: str | None = None,
) -> tuple[list[str], list[Any]]:
    prefix = f"{table_alias}."
    clauses = [f"{prefix}project_id = ?"]
    params: list[Any] = [project_id]
    _append_visible_exp_clause(conn, project_id, actor, clauses, params, column=f"{prefix}exp_id")
    if not flag(args, "--include-archived"):
        clauses.append(f"{prefix}status != 'archived'")
    status = _require_option_choice(command_arg(args, "--status"), "--status", EXPERIMENT_STATUSES)
    if status:
        clauses.append(f"{prefix}status = ?")
        params.append(status)
    source_id_filter = _complete_id_option(args, "--source-id", "src")
    if source_id_filter:
        clauses.append(f"{prefix}source_id = ?")
        params.append(source_id_filter)
    config_version_filter = _parse_positive_int_option(args, "--config-version")
    if config_version_filter is not None:
        clauses.append(f"{prefix}bound_config_version = ?")
        params.append(config_version_filter)
    _require_ordered_time_range(args, "--created-after", "--created-before")
    _require_ordered_time_range(args, "--updated-after", "--updated-before")
    for option, column, op in [
        ("--created-after", "created_at", ">="),
        ("--created-before", "created_at", "<="),
        ("--updated-after", "updated_at", ">="),
        ("--updated-before", "updated_at", "<="),
    ]:
        value = command_arg(args, option)
        if value:
            clauses.append(f"{prefix}{column} {op} ?")
            params.append(parse_rfc3339_utc(value))
    for tag in command_args(args, "--tag"):
        tag_slug = _tag_slug(tag)
        clauses.append(
            f"""
            EXISTS (
              SELECT 1 FROM experiment_tags et
              WHERE et.project_id = {prefix}project_id
                AND et.exp_id = {prefix}exp_id
                AND et.tag_slug = ?
            )
            """
        )
        params.append(tag_slug)
    name_query = command_arg(args, "--name-query") or ""
    if name_query:
        _register_observe_text_predicates(conn)
        clauses.append(
            f"alab_record_json_field_casefold_contains({prefix}metadata_json, 'name', ?) = 1"
        )
        params.append(name_query)
    if search_query is not None:
        _append_experiment_search_clause(conn, clauses, params, table_alias, actor, search_query)
    return clauses, params


def _experiment_candidate_sql(
    conn, project_id: str, actor: Actor, args: list[str], *, search_query: str | None = None
) -> tuple[str, list[Any]]:
    clauses, params = _experiment_query_clauses(
        conn, project_id, actor, args, search_query=search_query
    )
    return (
        f"SELECT e.rowid AS alab_exp_rowid, e.* FROM experiments e WHERE {' AND '.join(clauses)}",
        params,
    )


def _experiment_requested_sort_field(args: list[str], *, default: str) -> str:
    sort_text = command_arg(args, "--sort", default=default) or default
    field, _sep, _direction = sort_text.partition(":")
    return field


def _experiment_order_limit_clause(
    args: list[str],
    *,
    default: str,
    exp_alias: str,
    rowid_expression: str,
    reward_expression: str | None = None,
) -> tuple[str, tuple[Any, ...]]:
    allowed = {
        "created": f"{exp_alias}.created_at",
        "updated": f"{exp_alias}.updated_at",
        "name": f"alab_casefold(json_extract({exp_alias}.metadata_json, '$.name'))",
        "status": f"LOWER({exp_alias}.status)",
    }
    if reward_expression is not None:
        allowed["reward"] = reward_expression
    return _sql_order_limit_clause(
        args,
        default=default,
        allowed=allowed,
        subject="experiments",
        tie_breakers=(rowid_expression,),
    )


def _best_run_from_joined_experiment_row(row: Any) -> dict[str, Any] | None:
    if row["alab_best_run_id"] is None:
        return None
    return {
        "run_id": row["alab_best_run_id"],
        "exp_id": row["exp_id"],
        "commit_sha": row["alab_best_commit_sha"],
        "config_version": row["alab_best_config_version"],
        "reward_value": row["alab_best_reward_value"],
        "reward_parse_status": row["alab_best_reward_parse_status"],
        "archive_status": row["alab_best_archive_status"],
        "ended_at": row["alab_best_ended_at"],
    }


def _reward_bound_sql(
    column: str, reward_min: float | None, reward_max: float | None
) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if reward_min is not None:
        clauses.append(f"{column} >= ?")
        params.append(reward_min)
    if reward_max is not None:
        clauses.append(f"{column} <= ?")
        params.append(reward_max)
    return clauses, params


def _best_runs_for_experiments(
    conn,
    *,
    project_id: str,
    exp_ids: list[str],
    direction: str,
    config_version: int | None = None,
    reward_config_versions: list[int] | None = None,
    include_archived_runs: bool = False,
) -> dict[str, Any]:
    if not exp_ids:
        return {}
    run_clauses, run_params = _best_run_sql_clauses(
        project_id=project_id,
        config_version=config_version,
        reward_config_versions=reward_config_versions,
        include_archived_runs=include_archived_runs,
        exp_ids=exp_ids,
    )
    rows = all_rows(
        conn,
        f"""
        SELECT * FROM (
          SELECT r.*,
            ROW_NUMBER() OVER (
              PARTITION BY r.exp_id
              ORDER BY {_best_run_window_order(direction)}
            ) AS alab_best_rank
          FROM runs r
          WHERE {" AND ".join(run_clauses)}
        )
        WHERE alab_best_rank = 1
        """,
        tuple(run_params),
    )
    return {row["exp_id"]: row for row in rows}


def _experiment_page_rows(
    conn,
    project_id: str,
    actor: Actor,
    args: list[str],
    *,
    search_query: str | None,
    sort_default: str,
) -> list[Any]:
    _register_observe_text_predicates(conn)
    candidate_sql, candidate_params = _experiment_candidate_sql(
        conn, project_id, actor, args, search_query=search_query
    )
    order_sql, order_params = _experiment_order_limit_clause(
        args,
        default=sort_default,
        exp_alias="e",
        rowid_expression="e.rowid",
    )
    return all_rows(conn, f"{candidate_sql} {order_sql}", (*candidate_params, *order_params))


def _experiment_rows_with_ranked_best(
    conn,
    project_id: str,
    actor: Actor,
    args: list[str],
    *,
    direction: str,
    config_version: int | None,
    reward_config_versions: list[int] | None,
    include_archived_runs: bool,
    reward_min: float | None,
    reward_max: float | None,
    search_query: str | None,
    sort_default: str,
) -> list[tuple[Any, dict[str, Any] | None]]:
    _register_observe_text_predicates(conn)
    candidate_sql, candidate_params = _experiment_candidate_sql(
        conn, project_id, actor, args, search_query=search_query
    )
    run_clauses, run_params = _best_run_sql_clauses(
        project_id=project_id,
        config_version=config_version,
        reward_config_versions=reward_config_versions,
        include_archived_runs=include_archived_runs,
    )
    outer_clauses, outer_params = _reward_bound_sql("rb.reward_value", reward_min, reward_max)
    outer_where = f"WHERE {' AND '.join(outer_clauses)}" if outer_clauses else ""
    order_sql, order_params = _experiment_order_limit_clause(
        args,
        default=sort_default,
        exp_alias="ce",
        rowid_expression="ce.alab_exp_rowid",
        reward_expression="rb.reward_value",
    )
    rows = all_rows(
        conn,
        f"""
        WITH candidate_experiments AS (
          {candidate_sql}
        ),
        ranked_best_runs AS (
          SELECT r.run_id, r.exp_id, r.commit_sha, r.config_version, r.reward_value,
                 r.reward_parse_status, r.archive_status, r.ended_at,
            ROW_NUMBER() OVER (
              PARTITION BY r.exp_id
              ORDER BY {_best_run_window_order(direction)}
            ) AS alab_best_rank
          FROM runs r
          JOIN candidate_experiments ce ON ce.exp_id = r.exp_id
          WHERE {" AND ".join(run_clauses)}
        )
        SELECT ce.*,
               rb.run_id AS alab_best_run_id,
               rb.commit_sha AS alab_best_commit_sha,
               rb.config_version AS alab_best_config_version,
               rb.reward_value AS alab_best_reward_value,
               rb.reward_parse_status AS alab_best_reward_parse_status,
               rb.archive_status AS alab_best_archive_status,
               rb.ended_at AS alab_best_ended_at
        FROM candidate_experiments ce
        LEFT JOIN ranked_best_runs rb ON rb.exp_id = ce.exp_id AND rb.alab_best_rank = 1
        {outer_where}
        {order_sql}
        """,
        (*candidate_params, *run_params, *outer_params, *order_params),
    )
    return [(row, _best_run_from_joined_experiment_row(row)) for row in rows]


def _experiment_list_search_rows_with_best(
    conn,
    project_id: str,
    actor: Actor,
    args: list[str],
    *,
    direction: str,
    reward_config_versions: list[int] | None,
    reward_min: float | None,
    reward_max: float | None,
    search_query: str | None,
    sort_default: str,
) -> list[tuple[Any, Any | None]]:
    sort_field = _experiment_requested_sort_field(args, default=sort_default)
    if sort_field == "reward" or reward_min is not None or reward_max is not None:
        return _experiment_rows_with_ranked_best(
            conn,
            project_id,
            actor,
            args,
            direction=direction,
            config_version=None,
            reward_config_versions=reward_config_versions,
            include_archived_runs=False,
            reward_min=reward_min,
            reward_max=reward_max,
            search_query=search_query,
            sort_default=sort_default,
        )
    rows = _experiment_page_rows(
        conn, project_id, actor, args, search_query=search_query, sort_default=sort_default
    )
    exp_ids = [row["exp_id"] for row in rows]
    best_by_exp = _best_runs_for_experiments(
        conn,
        project_id=project_id,
        exp_ids=exp_ids,
        direction=direction,
        reward_config_versions=reward_config_versions,
    )
    return [(row, best_by_exp.get(row["exp_id"])) for row in rows]


def _incomparable_best_run_count(
    conn,
    *,
    candidate_sql: str,
    candidate_params: list[Any],
    project_id: str,
    reward_config_versions: list[int] | None,
    include_archived_runs: bool,
) -> int:
    if reward_config_versions is None:
        return 0
    run_clauses, run_params = _best_run_sql_clauses(
        project_id=project_id,
        config_version=None,
        reward_config_versions=None,
        include_archived_runs=include_archived_runs,
    )
    version_clause, version_params = _sql_in_clause("r.config_version", reward_config_versions)
    run_clauses.append(f"NOT ({version_clause})")
    row = one(
        conn,
        f"""
        WITH candidate_experiments AS (
          {candidate_sql}
        )
        SELECT COUNT(*) AS count
        FROM runs r
        JOIN candidate_experiments ce ON ce.exp_id = r.exp_id
        WHERE {" AND ".join(run_clauses)}
        """,
        (*candidate_params, *run_params, *version_params),
    )
    return int(row["count"] if row else 0)


def _experiment_best_rows_with_excluded_count(
    conn,
    project_id: str,
    actor: Actor,
    args: list[str],
    *,
    direction: str,
    config_version: int | None,
    reward_config_versions: list[int] | None,
    include_archived_runs: bool,
    reward_min: float | None,
    reward_max: float | None,
) -> tuple[list[tuple[Any, dict[str, Any] | None]], int]:
    _register_observe_text_predicates(conn)
    candidate_sql, candidate_params = _experiment_candidate_sql(conn, project_id, actor, args)
    excluded_count = _incomparable_best_run_count(
        conn,
        candidate_sql=candidate_sql,
        candidate_params=candidate_params,
        project_id=project_id,
        reward_config_versions=reward_config_versions,
        include_archived_runs=include_archived_runs,
    )
    run_clauses, run_params = _best_run_sql_clauses(
        project_id=project_id,
        config_version=config_version,
        reward_config_versions=reward_config_versions,
        include_archived_runs=include_archived_runs,
    )
    outer_clauses, outer_params = _reward_bound_sql("rb.reward_value", reward_min, reward_max)
    outer_where = f"WHERE {' AND '.join(outer_clauses)}" if outer_clauses else ""
    reward_direction = "DESC" if direction == "maximize" else "ASC"
    limit, offset = _parse_limit_offset(args)
    rows = all_rows(
        conn,
        f"""
        WITH candidate_experiments AS (
          {candidate_sql}
        ),
        ranked_best_runs AS (
          SELECT r.run_id, r.exp_id, r.commit_sha, r.config_version, r.reward_value,
                 r.reward_parse_status, r.archive_status, r.ended_at,
            ROW_NUMBER() OVER (
              PARTITION BY r.exp_id
              ORDER BY {_best_run_window_order(direction)}
            ) AS alab_best_rank
          FROM runs r
          JOIN candidate_experiments ce ON ce.exp_id = r.exp_id
          WHERE {" AND ".join(run_clauses)}
        )
        SELECT ce.*,
               rb.run_id AS alab_best_run_id,
               rb.commit_sha AS alab_best_commit_sha,
               rb.config_version AS alab_best_config_version,
               rb.reward_value AS alab_best_reward_value,
               rb.reward_parse_status AS alab_best_reward_parse_status,
               rb.archive_status AS alab_best_archive_status,
               rb.ended_at AS alab_best_ended_at
        FROM candidate_experiments ce
        JOIN ranked_best_runs rb ON rb.exp_id = ce.exp_id AND rb.alab_best_rank = 1
        {outer_where}
        ORDER BY rb.reward_value {reward_direction}, rb.ended_at DESC, ce.exp_id ASC
        LIMIT ? OFFSET ?
        """,
        (*candidate_params, *run_params, *outer_params, limit, offset),
    )
    return [(row, _best_run_from_joined_experiment_row(row)) for row in rows], excluded_count


def _experiment_result_block(
    conn,
    row: Any,
    *,
    best_run: Any | None = None,
    reward_parse_status: str | None = None,
) -> ResultBlock:
    meta = experiment_metadata_obj(row["metadata_json"])
    source = one(conn, "SELECT source_ref FROM sources WHERE source_id = ?", (row["source_id"],))
    tags = _tag_values(conn, row["exp_id"])
    return ResultBlock(
        "experiment",
        [
            ("project id", row["project_id"]),
            ("exp id", row["exp_id"]),
            ("experiment name", meta.get("name")),
            ("experiment status", row["status"]),
            ("source id", row["source_id"]),
            ("source ref", source["source_ref"] if source else None),
            ("tag", tags),
            ("latest run id", row["latest_run_id"]),
            ("latest commit", row["latest_commit"]),
            ("final run id", row["final_run_id"]),
            ("final commit", row["final_commit"]),
            ("best run id", best_run["run_id"] if best_run else None),
            ("reward", best_run["reward_value"] if best_run else None),
            (
                "reward parse status",
                (best_run["reward_parse_status"] if best_run else reward_parse_status) or "none",
            ),
            ("created at", row["created_at"]),
            ("updated at", row["updated_at"]),
            ("closed at", row["closed_at"]),
            ("archived at", row["archived_at"]),
        ],
    )


def _require_experiment_query_options_at_most_once(args: list[str], *, allow_sort: bool) -> None:
    options = [
        "--include-archived",
        "--status",
        "--name-query",
        "--source-id",
        "--config-version",
        "--created-after",
        "--created-before",
        "--updated-after",
        "--updated-before",
        "--reward-min",
        "--reward-max",
        "--limit",
        "--offset",
    ]
    if allow_sort:
        options.append("--sort")
    require_options_at_most_once(args, tuple(options))


def cmd_exp_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--status",
            "--name-query",
            "--source-id",
            "--config-version",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--tag",
            "--reward-min",
            "--reward-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    _require_experiment_query_options_at_most_once(args, allow_sort=True)
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "exp list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        identity, direction = _optional_best_context(conn, project)
        reward_config_versions = _reward_identity_config_versions(conn, project_id, identity)
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        rows_with_best = _experiment_list_search_rows_with_best(
            conn,
            project_id,
            actor,
            args,
            direction=direction,
            reward_config_versions=reward_config_versions,
            reward_min=reward_min,
            reward_max=reward_max,
            search_query=None,
            sort_default="updated:desc",
        )
        return [_experiment_result_block(conn, row, best_run=best) for row, best in rows_with_best]
    finally:
        conn.close()


def cmd_exp_search(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--query",
            "--include-archived",
            "--status",
            "--name-query",
            "--source-id",
            "--config-version",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--tag",
            "--reward-min",
            "--reward-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(args, ("--query",))
    _require_experiment_query_options_at_most_once(args, allow_sort=True)
    query = command_arg(args, "--query", required=True).casefold()
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "exp search accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        identity, direction = _optional_best_context(conn, project)
        reward_config_versions = _reward_identity_config_versions(conn, project_id, identity)
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        rows_with_best = _experiment_list_search_rows_with_best(
            conn,
            project_id,
            actor,
            args,
            direction=direction,
            reward_config_versions=reward_config_versions,
            reward_min=reward_min,
            reward_max=reward_max,
            search_query=query,
            sort_default="updated:desc",
        )
        return [_experiment_result_block(conn, row, best_run=best) for row, best in rows_with_best]
    finally:
        conn.close()


def cmd_exp_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--include-archived"))
    require_options_at_most_once(args, ("--include-archived",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    exp_id = optional_positional_selector(args, "exp show accepts exactly one experiment id")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        exp_id = _complete_id_or_missing(
            exp_id, prefix="exp", code="EXPERIMENT_NOT_FOUND", label="experiment id"
        )
        exp = one(
            conn,
            "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?",
            (project_id, exp_id),
        )
        if exp is None:
            if actor.actor_type == "token":
                raise AlabError("SCOPE_VIOLATION", "experiment is not visible or not found")
            raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
        if not _exp_visible(conn, project_id, actor, exp["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "experiment is not visible or not found")
        identity, direction = _optional_best_context(conn, project)
        best, _excluded = _best_run_for_experiment(
            conn,
            project_id=project_id,
            exp_id=exp["exp_id"],
            direction=direction,
            reward_identity=identity,
            include_archived_runs=flag(args, "--include-archived"),
        )
        return [_experiment_result_block(conn, exp, best_run=best)]
    finally:
        conn.close()


def cmd_exp_best(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--status",
            "--name-query",
            "--source-id",
            "--config-version",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--tag",
            "--reward-min",
            "--reward-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    _require_experiment_query_options_at_most_once(args, allow_sort=False)
    require_options_at_most_once(args, ("--sort",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    if command_arg(args, "--sort") is not None:
        raise AlabError("CONFIG_INVALID", "--sort is not supported for experiment best")
    require_positional_count(args, 0, "exp best accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        config_version, identity, direction = _best_context(conn, project, args)
        reward_config_versions = _reward_identity_config_versions(conn, project_id, identity)
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        rows_with_best, excluded_count = _experiment_best_rows_with_excluded_count(
            conn,
            project_id,
            actor,
            args,
            direction=direction,
            config_version=config_version,
            reward_config_versions=reward_config_versions,
            include_archived_runs=flag(args, "--include-archived"),
            reward_min=reward_min,
            reward_max=reward_max,
        )
        blocks = [
            _experiment_result_block(conn, row, best_run=best) for row, best in rows_with_best
        ]
        if excluded_count:
            blocks.append(
                ResultBlock(
                    "warning",
                    [
                        ("warning code", "BEST_INCOMPARABLE_RUNS_EXCLUDED"),
                        (
                            "warning reason",
                            "runs with incompatible reward policy identity were excluded",
                        ),
                        ("excluded count", excluded_count),
                    ],
                )
            )
        return blocks
    finally:
        conn.close()
