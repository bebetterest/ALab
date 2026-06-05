# ALab Examples

These examples are runnable from the repository root and keep generated state in
ignored `.run/` directories. Secrets are written only under `.run/secrets/`.

## Overview

The examples are ordered from the smallest local loop to the most complete
agent-driven external benchmark. Each example is a runnable project demo with a
different task shape, runner boundary, and evidence workflow:

- [local_agent_scoreboard](local_agent_scoreboard/) is the shortest local loop:
  edit one deterministic scorer, parse stdout reward, capture artifacts, and
  submit a result.
- [free_evaluation_intro_site](free_evaluation_intro_site/) is the open-ended
  manual-review loop: complete a Chinese static introduction site for a Korean
  drama and submit without an evaluator run.
- [docker_file_reward_artifacts](docker_file_reward_artifacts/) is a
  container-only operations task: assign clinic orders to warehouses under
  inventory, priority, cold-chain, and split-shipment constraints, then export
  captured artifacts.
- [harbor_verifier_minimal](harbor_verifier_minimal/) is a hidden-test task:
  improve an incident urgency classifier while the Harbor verifier keeps its
  test cases and detailed logs outside the worker surface.
- [collaboration_observe_lifecycle](collaboration_observe_lifecycle/) is a
  project-coordination task: create public experiments, continue from the best
  prior run, tag and annotate evidence, inspect a prior commit, and dry-run
  lifecycle cleanup.
- [dashboard_showcase](dashboard_showcase/) generates a rich ALab home with
  multiple projects, experiments, runs, logs, artifacts, audit entries,
  feedback, caches, capabilities, catalogs, and locks for dashboard inspection.
- [skydiscover_circle_packing_codex](skydiscover_circle_packing_codex/) is the
  full Codex/SkyDiscover task: use an isolated worktree worker to improve the
  circle-packing benchmark while ALab records runs, metrics, logs, and reports.
- [templates](templates/) is a template library rather than one demo: copy one
  of its multi-instance TSP templates to start from a complete local, Docker,
  Harbor, SkyDiscover Python, or SkyDiscover Docker project skeleton.

Use `--dry-run` first when learning an example. It prints the command shape and
paths without mutating the example state.

## Example Matrix

| Example | Demo task | Runner / adapter | Extra requirements | Main coverage | Commands |
| --- | --- | --- | --- | --- | --- |
| [local_agent_scoreboard](local_agent_scoreboard/) | Improve a deterministic scoring candidate and submit the best run. | local | optional Codex CLI | local runner, stdout reward, artifacts, submit, isolated worker launch | `scripts/setup_project.sh`, `scripts/run_manual_demo.sh`, `scripts/run_codex_worker.sh` |
| [free_evaluation_intro_site](free_evaluation_intro_site/) | Complete a Simplified Chinese static introduction site for `모두가 자신의 무가치함과 싸우고 있다`. | none / free evaluation | none beyond ALab dev env | no evaluator, `not_required` validation, direct submit, manual review | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [docker_file_reward_artifacts](docker_file_reward_artifacts/) | Build a containerized clinic-order fulfillment planner over inventory and cold-chain constraints. | Docker | Docker daemon | Dockerfile runner, file reward, manifest/summary artifacts, artifact export | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [harbor_verifier_minimal](harbor_verifier_minimal/) | Improve an incident-ticket urgency classifier scored by hidden Harbor verifier cases. | Harbor | Docker daemon | Harbor source import, private verifier assets, hidden verifier logs, Harbor reward | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [collaboration_observe_lifecycle](collaboration_observe_lifecycle/) | Coordinate two public incident-triage experiments and continue from the best run. | local | none beyond ALab dev env | public create, from-exp best, tags, annotations, inspection, remove dry-run | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [dashboard_showcase](dashboard_showcase/) | Generate a rich ALab home for root dashboard browsing. | local fixture | none beyond ALab dev env | dashboard summary/detail data, projects, experiments, runs, logs, artifacts, audit, feedback, system diagnostics | `scripts/create_demo_home.py`, `scripts/run_dashboard.sh` |
| [skydiscover_circle_packing_codex](skydiscover_circle_packing_codex/) | Improve the SkyDiscover circle-packing benchmark with one Codex worker. | SkyDiscover Python | Codex CLI, network, uv dependency install | SkyDiscover catalog, Python evaluator, isolated worker protocol | `scripts/setup_project.sh`, `scripts/run_single_worker.sh` |
| [templates](templates/) | Copy a complete default multi-instance TSP template for one runner family. | local, Docker, Harbor, SkyDiscover Python, SkyDiscover Docker | Docker only for Docker-bound templates | reusable project configs, validation scripts, starter/reference solutions, setup/run scripts | `templates/<template>/scripts/setup_project.sh`, `templates/<template>/scripts/run_demo.sh` |

## Suggested Path

Start with `free_evaluation_intro_site` when you want to see the no-run manual
review path. Use `local_agent_scoreboard` for the basic project/run/submit loop.
Then use `collaboration_observe_lifecycle` to understand experiment lineage and
observe commands. Use `dashboard_showcase` when you want a populated local home
for browser dashboard inspection. Use `docker_file_reward_artifacts` and
`harbor_verifier_minimal` when validating runner and verifier boundaries. Use
`skydiscover_circle_packing_codex` when you need the full single-worker Codex
and SkyDiscover flow. Use `templates` when you want a copyable default project
shape instead of a completed scenario walkthrough.

## Isolation Pattern

When an example launches Codex, the worker uses the experiment worktree as
`codex exec -C` with `--sandbox workspace-write`. Worker launches do not add the repository root, the whole
`.run/` directory, `.run/secrets`, or `project.env`. They add only the ALab
home, uv cache, pycache, and non-secret shared directories required for
`alab run`/`submit` state. Treat the worktree as the only editable source
surface; added side directories are CLI state only.

Setup scripts may store a project admin key in ignored `.run/secrets/`, but
worker processes must not receive that key, root keys, secret files, or secret
directories.
