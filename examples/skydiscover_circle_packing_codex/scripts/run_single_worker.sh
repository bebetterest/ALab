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
Usage: scripts/run_single_worker.sh [--dry-run]

Creates one ALab experiment and launches one Codex worker inside the experiment
worktree. Run setup_project.sh first.
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
WORKTREE_ROOT="${ALAB_EXAMPLE_WORKTREE_ROOT:-$RUN_DIR/worktrees}"
SHARED_DIR="${ALAB_SHARED_DIR:-$RUN_DIR/shared}"
LOG_DIR="$RUN_DIR/logs"
EXP_NAME="${EXP_NAME:-codex-circle-single}"
CODEX_MODEL="${CODEX_MODEL:-}"
ALAB_BIN="${ALAB_BIN:-uv run --frozen --project $REPO_ROOT alab}"
ALAB_EXAMPLE_HOME="${ALAB_EXAMPLE_HOME:-$RUN_DIR/alab-home}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$RUN_DIR/uv-cache}"
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$RUN_DIR/pycache}"
ALAB_CMD_PREFIX="${ALAB_CMD_PREFIX:-UV_CACHE_DIR=$UV_CACHE_DIR PYTHONPYCACHEPREFIX=$PYTHONPYCACHEPREFIX $ALAB_BIN --home $ALAB_EXAMPLE_HOME}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would create one experiment and launch a Codex worker.

Project env:   $PROJECT_ENV
Experiment:    $EXP_NAME
Worktree root: $WORKTREE_ROOT
Codex model:   ${CODEX_MODEL:-<codex default>}

Commands:
  source $PROJECT_ENV
  eval "\$ALAB_CMD_PREFIX exp create --project \$ALAB_PROJECT_ID --name $EXP_NAME --path $WORKTREE_ROOT/$EXP_NAME"
  env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY -u ALAB_KEY ALAB_CMD_PREFIX="\$ALAB_CMD_PREFIX" codex exec -C <worktree> --add-dir \$ALAB_EXAMPLE_HOME --add-dir \$UV_CACHE_DIR --add-dir \$PYTHONPYCACHEPREFIX --add-dir $SHARED_DIR ${CODEX_MODEL:+-m "$CODEX_MODEL"} --sandbox workspace-write - < $EXAMPLE_DIR/prompts/worker.md
EOF
  exit 0
fi

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo "missing $PROJECT_ENV; run scripts/setup_project.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ENV"

mkdir -p "$WORKTREE_ROOT" "$SHARED_DIR" "$LOG_DIR" "$UV_CACHE_DIR" "$PYTHONPYCACHEPREFIX"
read -r -a ALAB_CMD <<< "$ALAB_BIN"

run_alab() {
  UV_CACHE_DIR="$UV_CACHE_DIR" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}

extract_field() {
  local label="$1"
  local file="$2"
  awk -v key="$label" 'index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }' "$file"
}

CREATE_LOG="$LOG_DIR/single-exp-create.log"
WORKER_LOG="$LOG_DIR/single-worker.log"
CODEX_MODEL_ARGS=()
if [[ -n "$CODEX_MODEL" ]]; then
  CODEX_MODEL_ARGS=(-m "$CODEX_MODEL")
fi

run_alab exp create --project "$ALAB_PROJECT_ID" --name "$EXP_NAME" --path "$WORKTREE_ROOT/$EXP_NAME" | tee "$CREATE_LOG"
WORKTREE_PATH="$(extract_field "worktree path" "$CREATE_LOG")"
EXP_ID="$(extract_field "exp id" "$CREATE_LOG")"

if [[ -z "$WORKTREE_PATH" || -z "$EXP_ID" ]]; then
  echo "failed to parse experiment output from $CREATE_LOG" >&2
  exit 1
fi

env -u ALAB_PROJECT_KEY \
  -u ALAB_ROOT_KEY \
  -u ALAB_KEY \
  ALAB_CMD_PREFIX="$ALAB_CMD_PREFIX" \
  codex exec -C "$WORKTREE_PATH" \
  --add-dir "$ALAB_EXAMPLE_HOME" \
  --add-dir "$UV_CACHE_DIR" \
  --add-dir "$PYTHONPYCACHEPREFIX" \
  --add-dir "$SHARED_DIR" \
  ${CODEX_MODEL_ARGS[@]+"${CODEX_MODEL_ARGS[@]}"} \
  --sandbox workspace-write \
  - < "$EXAMPLE_DIR/prompts/worker.md" | tee "$WORKER_LOG"

echo "Single worker experiment: $EXP_ID"
echo "Worker log: $WORKER_LOG"
