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

Creates two public incident-triage experiments, continues the second from the
first best run, adds evidence, creates an inspection checkout, and dry-runs
lifecycle removal.
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
INSPECTION_ROOT="${ALAB_INSPECTION_ROOT:-$RUN_DIR/inspection}"

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<EOF
Would run collaboration/observe/lifecycle demo.

Project env: $PROJECT_ENV
Worktrees:   $WORKTREE_ROOT
Inspection:  $INSPECTION_ROOT
EOF
  exit 0
fi

if [[ ! -f "$PROJECT_ENV" ]]; then
  echo "missing $PROJECT_ENV; run scripts/setup_project.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ENV"
mkdir -p "$LOG_DIR" "$REPORT_DIR" "$WORKTREE_ROOT" "$INSPECTION_ROOT"
read -r -a ALAB_CMD <<< "${ALAB_BIN:-uv run --frozen --project $REPO_ROOT alab}"
run_alab() {
  UV_CACHE_DIR="$UV_CACHE_DIR" PYTHONPYCACHEPREFIX="$PYTHONPYCACHEPREFIX" "${ALAB_CMD[@]}" --home "$ALAB_EXAMPLE_HOME" "$@"
}
extract_field() {
  local label="$1"
  local file="$2"
  awk -v key="$label" 'index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }' "$file"
}

STEP1_CREATE="$LOG_DIR/step1-create.log"
STEP1_RUN="$LOG_DIR/step1-run.log"
STEP1_SUBMIT="$LOG_DIR/step1-submit.log"
STEP2_CREATE="$LOG_DIR/step2-create.log"
STEP2_RUN="$LOG_DIR/step2-run.log"

run_alab exp create --project "$ALAB_PROJECT_ID" --name "collab-step-1" --path "$WORKTREE_ROOT/collab-step-1" | tee "$STEP1_CREATE"
STEP1_EXP="$(extract_field "exp id" "$STEP1_CREATE")"
STEP1_WORKTREE="$(extract_field "worktree path" "$STEP1_CREATE")"
perl -0pi -e 's/POLICY = "baseline_queue"/POLICY = "severity_first"/' "$STEP1_WORKTREE/solver.py"
(cd "$STEP1_WORKTREE" && run_alab run --message "incident triage severity-first step") | tee "$STEP1_RUN"
(cd "$STEP1_WORKTREE" && run_alab submit --message "incident triage severity-first candidate" --summary "Step one prioritizes critical incidents over queue order." --feedback "The latest run passed and is used as the from-exp source." --ref none) | tee "$STEP1_SUBMIT"

run_alab exp create --project "$ALAB_PROJECT_ID" --name "collab-step-2" --from-exp "$STEP1_EXP" --from-commit best --path "$WORKTREE_ROOT/collab-step-2" | tee "$STEP2_CREATE"
STEP2_EXP="$(extract_field "exp id" "$STEP2_CREATE")"
STEP2_WORKTREE="$(extract_field "worktree path" "$STEP2_CREATE")"
perl -0pi -e 's/POLICY = "severity_first"/POLICY = "sla_balanced"/; s/ENABLE_RUNBOOK_SHORTCUTS = False/ENABLE_RUNBOOK_SHORTCUTS = True/; s/ESCALATE_SECURITY = False/ESCALATE_SECURITY = True/' "$STEP2_WORKTREE/solver.py"
(cd "$STEP2_WORKTREE" && run_alab run --message "incident triage SLA-balanced step from best") | tee "$STEP2_RUN"
(cd "$STEP2_WORKTREE" && run_alab exp tag add "$STEP2_EXP" demo-best) | tee "$LOG_DIR/step2-tag.log"
(cd "$STEP2_WORKTREE" && run_alab annotate add --target "exp:$STEP2_EXP" --body "Step two continues from step one best, adds runbook shortcuts, and escalates security incidents.") | tee "$LOG_DIR/step2-annotation.log"

run_alab --key "$ALAB_PROJECT_KEY" exp checkout "$STEP1_EXP" --project "$ALAB_PROJECT_ID" --path "$INSPECTION_ROOT/step1-best" --commit best | tee "$LOG_DIR/inspection-checkout.log"
run_alab --key "$ALAB_PROJECT_KEY" exp archive "$STEP1_EXP" --project "$ALAB_PROJECT_ID" | tee "$LOG_DIR/step1-archive.log"
run_alab --key "$ALAB_PROJECT_KEY" exp remove "$STEP1_EXP" --project "$ALAB_PROJECT_ID" --cascade --dry-run | tee "$LOG_DIR/step1-remove-dry-run.log"
run_alab --key "$ALAB_PROJECT_KEY" exp best --project "$ALAB_PROJECT_ID" | tee "$LOG_DIR/best.log"
run_alab --key "$ALAB_PROJECT_KEY" annotations list --project "$ALAB_PROJECT_ID" --target-type experiment --target-id "$STEP2_EXP" | tee "$LOG_DIR/annotations.log"

cat > "$REPORT_DIR/report.md" <<EOF
# Collaboration Incident Triage Lifecycle Report

- Step 1 experiment: \`$STEP1_EXP\`
- Step 2 experiment: \`$STEP2_EXP\`
- Step 1 inspection checkout: \`$INSPECTION_ROOT/step1-best\`
- Best log: \`$LOG_DIR/best.log\`
- Remove dry-run log: \`$LOG_DIR/step1-remove-dry-run.log\`
EOF

echo "Report written: $REPORT_DIR/report.md"
