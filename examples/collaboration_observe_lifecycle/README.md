# Collaboration Observe Lifecycle Example

This example uses the local runner to demonstrate ALab collaboration behavior:
public experiment creation, `--from-exp best`, tags, annotations, inspection
checkout, archive, and remove dry-run.

## Demo Task

The editable source is an incident triage scheduler. It reads
`source/data/incidents.json`, orders work under a ten-hour response budget, and
writes `result.json` plus `triage_plan.md`.

`scripts/run_demo.sh` creates a first public experiment that changes queue
order into severity-first triage and submits it. Then it creates a second public
experiment from the first experiment's best commit, enables runbook shortcuts
and security escalation, records tags and annotations, creates an inspection
checkout, archives the first experiment, and dry-runs cascade removal.

Task shape:

- Editable file: `source/solver.py`.
- Input data: `source/data/incidents.json`, a synthetic operations queue with
  severity, category, SLA, affected users, and runbook metadata.
- Baseline behavior: process incidents in creation order, which misses urgent
  SLA/security work.
- Step 1 improvement: `severity_first` ordering in a public experiment, then
  `alab submit`.
- Step 2 improvement: create a second public experiment from step 1's `best`
  commit, switch to SLA-balanced ranking, enable runbook shortcuts, and
  escalate security incidents.
- Captured evidence: `result.json`, `triage_plan.md`, run logs, experiment tag,
  annotation, inspection checkout, archive output, and remove dry-run output.

This example is intentionally about project coordination rather than one runner
feature. It shows how a controller can keep lineage and evidence visible while
workers operate only through their worktree tokens.

## Run

```sh
examples/collaboration_observe_lifecycle/scripts/setup_project.sh --dry-run
examples/collaboration_observe_lifecycle/scripts/setup_project.sh
examples/collaboration_observe_lifecycle/scripts/run_demo.sh
```

## What It Covers

- no-key public `exp create` for bootstrap;
- continuation with `--from-exp <exp_id> --from-commit best`;
- token-scoped run, tag, annotation, and artifact-producing commands from worktrees;
- admin inspection checkout and lifecycle dry-run;
- observe-style evidence logs under `.run/logs`.

## Security Notes

The project admin key is stored only in `.run/secrets/project.env`. Worktree
operations use the token written by ALab into each experiment worktree.
