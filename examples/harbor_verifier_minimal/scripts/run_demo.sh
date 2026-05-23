#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$EXAMPLE_DIR/../.." && pwd)"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/run_demo.sh [--dry-run]

Runs one Harbor-backed incident-priority experiment and records visible plus
hidden-log commands.
EOF
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

RUN_DIR="$EXAMPLE_DIR/.run"
PROJECT_ENV="$RUN_DIR/secrets/project.env"
LOG_DIR="$RUN_DIR/logs"
REPORT_DIR="${ALAB_REPORT_DIR:-$RUN_DIR/reports}"
WORKTREE_ROOT="${ALAB_EXAMPLE_WORKTREE_ROOT:-$RUN_DIR/worktrees}"
EXP_NAME="${EXP_NAME:-harbor-verifier-demo}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would run the Harbor verifier demo.

Project env: $PROJECT_ENV
Experiment:  $EXP_NAME
Worktree:    $WORKTREE_ROOT/$EXP_NAME
EOF
  exit 0
fi

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo "missing $PROJECT_ENV; run scripts/setup_project.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ENV"
mkdir -p "$LOG_DIR" "$REPORT_DIR" "$WORKTREE_ROOT"
read -r -a ALAB_CMD <<< "${ALAB_BIN:-uv run --frozen --project $REPO_ROOT alab}"
run_alab() {
  UV_CACHE_DIR="$UV_CACHE_DIR" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}
extract_field() {
  local label="$1"
  local file="$2"
  awk -v key="$label" 'index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }' "$file"
}

CREATE_LOG="$LOG_DIR/harbor-exp-create.log"
RUN_LOG="$LOG_DIR/harbor-run.log"
LOGS_LOG="$LOG_DIR/harbor-logs-list.log"

run_alab exp create --project "$ALAB_PROJECT_ID" --name "$EXP_NAME" --path "$WORKTREE_ROOT/$EXP_NAME" | tee "$CREATE_LOG"
WORKTREE_PATH="$(extract_field "worktree path" "$CREATE_LOG")"
EXP_ID="$(extract_field "exp id" "$CREATE_LOG")"

perl -0pi -e 's/"breach": 0\.00/"breach": 0.32/; s/"unable to login": 0\.00/"unable to login": 0.22/; s/"customer impact": 0\.00/"customer impact": 0.16/; s/THRESHOLD = 0\.65/THRESHOLD = 0.35/' "$WORKTREE_PATH/main.py"
(cd "$WORKTREE_PATH" && run_alab run --message "harbor incident priority verifier run") | tee "$RUN_LOG"
run_alab --key "$ALAB_PROJECT_KEY" logs list --project "$ALAB_PROJECT_ID" --include-hidden | tee "$LOGS_LOG"

cat > "$REPORT_DIR/report.md" <<EOF
# Harbor Incident Priority Verifier Report

- Experiment: \`$EXP_ID\`
- Worktree: \`$WORKTREE_PATH\`
- Run log: \`$RUN_LOG\`
- Hidden-capable logs list: \`$LOGS_LOG\`
EOF

echo "Report written: $REPORT_DIR/report.md"
