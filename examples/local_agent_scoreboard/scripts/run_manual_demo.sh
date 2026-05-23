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
Usage: scripts/run_manual_demo.sh [--dry-run]

Creates one experiment, applies a deterministic source edit, runs ALab, submits,
and writes a compact report.
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
EXP_NAME="${EXP_NAME:-local-scoreboard-manual}"
UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-https://pypi.org/simple}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would create and run a local scoreboard experiment.

Project env: $PROJECT_ENV
Experiment:  $EXP_NAME
Worktree:    $WORKTREE_ROOT/$EXP_NAME
uv index:    $UV_DEFAULT_INDEX
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
  UV_CACHE_DIR="$UV_CACHE_DIR" UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}

extract_field() {
  local label="$1"
  local file="$2"
  awk -v key="$label" 'index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }' "$file"
}

CREATE_LOG="$LOG_DIR/manual-exp-create.log"
RUN_LOG="$LOG_DIR/manual-run.log"
SUBMIT_LOG="$LOG_DIR/manual-submit.log"

run_alab exp create --project "$ALAB_PROJECT_ID" --name "$EXP_NAME" --path "$WORKTREE_ROOT/$EXP_NAME" | tee "$CREATE_LOG"
WORKTREE_PATH="$(extract_field "worktree path" "$CREATE_LOG")"
EXP_ID="$(extract_field "exp id" "$CREATE_LOG")"

perl -0pi -e 's/SCORE = 0\.40/SCORE = 0.82/; s/STRATEGY = "baseline constant"/STRATEGY = "manual deterministic improvement"/' "$WORKTREE_PATH/solution.py"

(cd "$WORKTREE_PATH" && run_alab run --message "manual local scoreboard improvement") | tee "$RUN_LOG"
(cd "$WORKTREE_PATH" && run_alab submit --message "manual local scoreboard candidate" --summary "Raised the deterministic example score." --feedback "The latest run passed and produced score.json." --ref none) | tee "$SUBMIT_LOG"

BEST_LOG="$LOG_DIR/manual-best.log"
run_alab --key "$ALAB_PROJECT_KEY" exp best --project "$ALAB_PROJECT_ID" | tee "$BEST_LOG"

cat > "$REPORT_DIR/report.md" <<EOF
# Local Agent Scoreboard Report

- Experiment: \`$EXP_ID\`
- Worktree: \`$WORKTREE_PATH\`
- Run log: \`$RUN_LOG\`
- Submit log: \`$SUBMIT_LOG\`
- Best log: \`$BEST_LOG\`
EOF

echo "Report written: $REPORT_DIR/report.md"
