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

Runs one Docker-backed fulfillment-planner experiment and exports the first
captured artifact.
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
EXP_NAME="${EXP_NAME:-docker-file-reward-demo}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would run the Docker file-reward demo.

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

CREATE_LOG="$LOG_DIR/docker-exp-create.log"
RUN_LOG="$LOG_DIR/docker-run.log"
ARTIFACT_LOG="$LOG_DIR/docker-artifacts.log"
EXPORT_PATH="$REPORT_DIR/exported-artifact.txt"

run_alab exp create --project "$ALAB_PROJECT_ID" --name "$EXP_NAME" --path "$WORKTREE_ROOT/$EXP_NAME" | tee "$CREATE_LOG"
WORKTREE_PATH="$(extract_field "worktree path" "$CREATE_LOG")"
EXP_ID="$(extract_field "exp id" "$CREATE_LOG")"

perl -0pi -e 's/STRATEGY = "baseline_fifo"/STRATEGY = "priority_compact"/; s/RESERVE_EXPRESS_STOCK = False/RESERVE_EXPRESS_STOCK = True/; s/MAX_SPLIT_WAREHOUSES = 4/MAX_SPLIT_WAREHOUSES = 2/' "$WORKTREE_PATH/main.py"
(cd "$WORKTREE_PATH" && run_alab run --message "docker file reward artifact run") | tee "$RUN_LOG"

run_alab --key "$ALAB_PROJECT_KEY" artifacts list --project "$ALAB_PROJECT_ID" | tee "$ARTIFACT_LOG"
ARTIFACT_ID="$(extract_field "artifact id" "$ARTIFACT_LOG")"
if [[ -n "$ARTIFACT_ID" ]]; then
  run_alab --key "$ALAB_PROJECT_KEY" artifacts export "$ARTIFACT_ID" --project "$ALAB_PROJECT_ID" --out "$EXPORT_PATH" --overwrite | tee "$LOG_DIR/docker-artifact-export.log"
fi

cat > "$REPORT_DIR/report.md" <<EOF
# Docker Fulfillment Planner Report

- Experiment: \`$EXP_ID\`
- Worktree: \`$WORKTREE_PATH\`
- Run log: \`$RUN_LOG\`
- Artifact list: \`$ARTIFACT_LOG\`
- Exported artifact: \`$EXPORT_PATH\`
EOF

echo "Report written: $REPORT_DIR/report.md"
