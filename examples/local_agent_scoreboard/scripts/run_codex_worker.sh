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
Usage: scripts/run_codex_worker.sh [--dry-run]

Creates one ALab experiment and launches Codex inside only that experiment
worktree, with ALab home/cache directories added for CLI state writes.
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
EXP_NAME="${EXP_NAME:-local-scoreboard-codex}"
CODEX_MODEL="${CODEX_MODEL:-}"
UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-https://pypi.org/simple}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would create one experiment and launch an isolated Codex worker.

Project env: $PROJECT_ENV
Experiment:  $EXP_NAME
Writable dirs:
  - <worktree> (Codex -C)
  - \$ALAB_EXAMPLE_HOME
  - \$UV_CACHE_DIR
  - \$PYTHONPYCACHEPREFIX
  - $SHARED_DIR
Forbidden dirs:
  - $REPO_ROOT
  - $RUN_DIR
  - $RUN_DIR/secrets
Unset credentials: ALAB_PROJECT_KEY, ALAB_ROOT_KEY, ALAB_KEY
uv index: $UV_DEFAULT_INDEX
Command:
  env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY -u ALAB_KEY ALAB_CMD_PREFIX="\$ALAB_CMD_PREFIX" UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" codex exec -C <worktree> --add-dir "\$ALAB_EXAMPLE_HOME" --add-dir "\$UV_CACHE_DIR" --add-dir "\$PYTHONPYCACHEPREFIX" --add-dir "$SHARED_DIR" --sandbox workspace-write - < $EXAMPLE_DIR/prompts/worker.md
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
read -r -a ALAB_CMD <<< "${ALAB_BIN:-uv run --frozen --project $REPO_ROOT alab}"

run_alab() {
  UV_CACHE_DIR="$UV_CACHE_DIR" UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}

canonical_dir() {
  (cd "$1" && pwd -P)
}

same_or_child() {
  local child="$1"
  local parent="$2"
  [[ "$child" == "$parent" || "$child" == "$parent"/* ]]
}

preflight_codex_worker() {
  if ! command -v codex >/dev/null 2>&1; then
    echo "missing codex CLI; install/login to Codex before running this worker" >&2
    exit 1
  fi
  local worktree_abs repo_abs run_abs secrets_abs dir_abs
  worktree_abs="$(canonical_dir "$WORKTREE_PATH")"
  repo_abs="$(canonical_dir "$REPO_ROOT")"
  run_abs="$(canonical_dir "$RUN_DIR")"
  secrets_abs="$(canonical_dir "$RUN_DIR/secrets")"
  if [[ "$worktree_abs" == "$repo_abs" || "$worktree_abs" == "$run_abs" ]] || same_or_child "$worktree_abs" "$secrets_abs"; then
    echo "refusing unsafe Codex worktree: $worktree_abs" >&2
    exit 1
  fi
  for dir in "$ALAB_EXAMPLE_HOME" "$UV_CACHE_DIR" "$PYTHONPYCACHEPREFIX" "$SHARED_DIR"; do
    mkdir -p "$dir"
    dir_abs="$(canonical_dir "$dir")"
    if same_or_child "$dir_abs" "$secrets_abs"; then
      echo "refusing to add secret directory to Codex sandbox: $dir_abs" >&2
      exit 1
    fi
  done
  echo "Codex worker preflight passed: worktree=$worktree_abs"
}

extract_field() {
  local label="$1"
  local file="$2"
  awk -v key="$label" 'index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }' "$file"
}

CREATE_LOG="$LOG_DIR/codex-exp-create.log"
WORKER_LOG="$LOG_DIR/codex-worker.log"
CODEX_MODEL_ARGS=()
if [[ -n "$CODEX_MODEL" ]]; then
  CODEX_MODEL_ARGS=(-m "$CODEX_MODEL")
fi

run_alab exp create --project "$ALAB_PROJECT_ID" --name "$EXP_NAME" --path "$WORKTREE_ROOT/$EXP_NAME" | tee "$CREATE_LOG"
WORKTREE_PATH="$(extract_field "worktree path" "$CREATE_LOG")"
if [[ -z "$WORKTREE_PATH" ]]; then
  echo "failed to parse worktree path from $CREATE_LOG" >&2
  exit 1
fi
preflight_codex_worker

env -u ALAB_PROJECT_KEY \
  -u ALAB_ROOT_KEY \
  -u ALAB_KEY \
  ALAB_CMD_PREFIX="$ALAB_CMD_PREFIX" \
  UV_DEFAULT_INDEX="$UV_DEFAULT_INDEX" \
  codex exec -C "$WORKTREE_PATH" \
  --add-dir "$ALAB_EXAMPLE_HOME" \
  --add-dir "$UV_CACHE_DIR" \
  --add-dir "$PYTHONPYCACHEPREFIX" \
  --add-dir "$SHARED_DIR" \
  ${CODEX_MODEL_ARGS[@]+"${CODEX_MODEL_ARGS[@]}"} \
  --sandbox workspace-write \
  - < "$EXAMPLE_DIR/prompts/worker.md" | tee "$WORKER_LOG"

echo "Worker log: $WORKER_LOG"
