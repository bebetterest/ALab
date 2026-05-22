#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$EXAMPLE_DIR/../.." && pwd)"
RUN_DIR="$EXAMPLE_DIR/.run"
PROJECT_ENV="$RUN_DIR/project.env"
LOG_DIR="$RUN_DIR/logs"
REPORT_PATH="$RUN_DIR/report.md"

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo "missing $PROJECT_ENV; run scripts/setup_project.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ENV"

mkdir -p "$LOG_DIR"
read -r -a ALAB_CMD <<< "${ALAB_BIN:-uv run --frozen --project $REPO_ROOT alab}"

run_alab() {
  UV_CACHE_DIR="$UV_CACHE_DIR" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}

run_alab --key "$ALAB_PROJECT_KEY" project show --project "$ALAB_PROJECT_ID" > "$LOG_DIR/report-project-show.log" 2>&1 || true
run_alab --key "$ALAB_PROJECT_KEY" exp list --project "$ALAB_PROJECT_ID" > "$LOG_DIR/report-experiments-list.log" 2>&1 || true
run_alab --key "$ALAB_PROJECT_KEY" runs list --project "$ALAB_PROJECT_ID" > "$LOG_DIR/report-runs-list.log" 2>&1 || true
run_alab --key "$ALAB_PROJECT_KEY" exp best --project "$ALAB_PROJECT_ID" > "$LOG_DIR/report-best.log" 2>&1 || true

python3 - "$ALAB_EXAMPLE_HOME" "$ALAB_PROJECT_ID" "$REPORT_PATH" "$LOG_DIR" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

home = Path(sys.argv[1])
project_id = sys.argv[2]
report_path = Path(sys.argv[3])
log_dir = Path(sys.argv[4])

db_path = home / "alab.db"


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def metadata_name(raw):
    try:
        return json.loads(raw).get("name", "")
    except Exception:
        return ""


rows = []
best = None
with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    validations = conn.execute(
        """
        SELECT validation_id, status, reward_value, reward_parse_status, started_at, ended_at, record_json
        FROM project_validations
        WHERE project_id = ?
        ORDER BY started_at
        """,
        (project_id,),
    ).fetchall()
    for row in validations:
        record = json.loads(row["record_json"])
        metrics = record.get("metrics", {})
        rows.append(
            {
                "phase": "baseline",
                "name": row["validation_id"],
                "status": row["status"],
                "reward": row["reward_value"],
                "sum_radii": metrics.get("sum_radii"),
                "target_ratio": metrics.get("target_ratio"),
                "validity": metrics.get("validity"),
                "eval_time": metrics.get("eval_time"),
                "commit": "",
                "run_id": "",
            }
        )

    runs = conn.execute(
        """
        SELECT r.run_id, r.exp_id, r.status, r.reward_value, r.reward_parse_status, r.commit_sha,
               r.started_at, r.ended_at, r.record_json, e.metadata_json
        FROM runs r
        JOIN experiments e ON e.exp_id = r.exp_id
        WHERE r.project_id = ?
        ORDER BY r.started_at
        """,
        (project_id,),
    ).fetchall()
    for row in runs:
        record = json.loads(row["record_json"])
        metrics = record.get("metrics", {})
        rows.append(
            {
                "phase": "run",
                "name": metadata_name(row["metadata_json"]) or row["exp_id"],
                "status": row["status"],
                "reward": row["reward_value"],
                "sum_radii": metrics.get("sum_radii"),
                "target_ratio": metrics.get("target_ratio"),
                "validity": metrics.get("validity"),
                "eval_time": metrics.get("eval_time"),
                "commit": row["commit_sha"][:12],
                "run_id": row["run_id"],
            }
        )

    best_row = conn.execute(
        """
        SELECT r.run_id, r.exp_id, r.reward_value, r.commit_sha, e.metadata_json
        FROM runs r
        JOIN experiments e ON e.exp_id = r.exp_id
        WHERE r.project_id = ? AND r.status = 'passed' AND r.reward_value IS NOT NULL
        ORDER BY r.reward_value DESC, r.started_at ASC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if best_row is not None:
        best = {
            "run_id": best_row["run_id"],
            "exp_id": best_row["exp_id"],
            "name": metadata_name(best_row["metadata_json"]) or best_row["exp_id"],
            "reward": best_row["reward_value"],
            "commit": best_row["commit_sha"],
        }

table_header = "| phase | name | status | reward | sum_radii | target_ratio | validity | eval_time | run id | commit |\n"
table_sep = "|---|---|---:|---:|---:|---:|---:|---:|---|---|\n"
table_rows = []
for row in rows:
    table_rows.append(
        "| {phase} | {name} | {status} | {reward} | {sum_radii} | {target_ratio} | {validity} | {eval_time} | {run_id} | {commit} |\n".format(
            phase=row["phase"],
            name=row["name"],
            status=row["status"],
            reward=fmt(row["reward"]),
            sum_radii=fmt(row["sum_radii"]),
            target_ratio=fmt(row["target_ratio"]),
            validity=fmt(row["validity"]),
            eval_time=fmt(row["eval_time"]),
            run_id=row["run_id"],
            commit=row["commit"],
        )
    )

best_lines = ["No passed run has a parsed reward yet."]
if best:
    best_lines = [
        f"- Best experiment: `{best['name']}` (`{best['exp_id']}`)",
        f"- Best run: `{best['run_id']}`",
        f"- Best reward: `{fmt(best['reward'])}`",
        f"- Best commit: `{best['commit']}`",
    ]

report = [
    "# ALab SkyDiscover Circle Packing Report\n\n",
    "This report is generated from the local ALab SQLite records for the example run.\n\n",
    "## Best Result\n\n",
    *[line + "\n" for line in best_lines],
    "\n## Result Table\n\n",
    table_header,
    table_sep,
    *table_rows,
    "\n## Command Logs\n\n",
    f"- Project show: `{log_dir / 'report-project-show.log'}`\n",
    f"- Experiments list: `{log_dir / 'report-experiments-list.log'}`\n",
    f"- Runs list: `{log_dir / 'report-runs-list.log'}`\n",
    f"- Best: `{log_dir / 'report-best.log'}`\n",
    "\n## Notes\n\n",
    "- `combined_score` is the optimization reward.\n",
    "- `sum_radii`, `target_ratio`, `validity`, and `eval_time` come from SkyDiscover evaluator metrics when present.\n",
    "- Project/admin keys are intentionally omitted from this report.\n",
]

report_path.write_text("".join(report), encoding="utf-8")
PY

echo "Report written: $REPORT_PATH"
