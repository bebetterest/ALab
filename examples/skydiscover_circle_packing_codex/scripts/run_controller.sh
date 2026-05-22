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
Usage: scripts/run_controller.sh [--dry-run]

Launches a Codex controller with the project admin key in its environment. The
controller creates three experiments and starts worker Codex agents without the
project admin key.
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
PROJECT_ENV="$RUN_DIR/project.env"
LOG_DIR="$RUN_DIR/logs"
CODEX_MODEL="${CODEX_MODEL:-}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would launch the Codex controller.

Project env: $PROJECT_ENV
Codex model: ${CODEX_MODEL:-<codex default>}

Command:
  source $PROJECT_ENV
  ALAB_PROJECT_KEY=<project-admin-key> codex exec -C $REPO_ROOT ${CODEX_MODEL:+-m "$CODEX_MODEL"} --sandbox workspace-write - < $EXAMPLE_DIR/prompts/controller.md
EOF
  exit 0
fi

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo "missing $PROJECT_ENV; run scripts/setup_project.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ENV"

mkdir -p "$LOG_DIR"
CONTROLLER_LOG="$LOG_DIR/controller.log"
CODEX_MODEL_ARGS=()
if [[ -n "$CODEX_MODEL" ]]; then
  CODEX_MODEL_ARGS=(-m "$CODEX_MODEL")
fi

codex exec -C "$REPO_ROOT" \
  "${CODEX_MODEL_ARGS[@]}" \
  --sandbox workspace-write \
  - < "$EXAMPLE_DIR/prompts/controller.md" | tee "$CONTROLLER_LOG"

echo "Controller log: $CONTROLLER_LOG"
