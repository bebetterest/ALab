# Docker File Reward Artifacts Example

This example demonstrates the Docker runner with a project Dockerfile, file
reward parsing, and exact artifact export on a container-only planning task.

## Demo Task

The editable source is a clinic-order fulfillment planner. It reads
`source/data/orders.json` and `source/data/warehouses.json`, then assigns orders
to warehouses while respecting inventory, cold-chain, priority, and
split-shipment constraints.

The baseline runs a simple FIFO strategy. `scripts/run_demo.sh` edits the
worktree candidate to use a priority-aware compact strategy, reserves express
stock for critical orders, runs ALab in Docker, captures `manifest.json`,
`summary.md`, and `reward.json`, then exports one captured artifact.

Task shape:

- Editable file: `source/main.py`.
- Input data: `source/data/orders.json` and `source/data/warehouses.json`.
- Constraints: stock limits, cold-chain compatibility, priority weight, SLA
  pressure, and split-shipment compactness.
- Baseline behavior: FIFO order allocation without express-stock reservation.
- Demo improvement: priority-aware allocation, compact splits, and express
  stock reservation for critical orders.
- Reward source: `run:reward.json`, with numeric metrics such as
  `weighted_fill`, `completed_weight`, `cold_chain_success`, and `compactness`.
  Keep this file as a string-to-finite-number map only; write explanations or
  case details to artifacts such as `summary.md`.
- Captured evidence: `manifest.json` for the allocation plan, `summary.md` for
  a human-readable digest, and `reward.json` for the parsed file reward.

This example is useful when validating Docker boundaries because the task only
runs through the Dockerfile runner. The captured artifact export shows that
ALab stores exact artifact bytes rather than a rendered summary.

## Requirements

- Docker daemon and an image pull/build path for `python:3.11-alpine`.
- The default ALab Python environment from this repository.

## Run

```sh
examples/docker_file_reward_artifacts/scripts/setup_project.sh --dry-run
examples/docker_file_reward_artifacts/scripts/setup_project.sh
examples/docker_file_reward_artifacts/scripts/run_demo.sh
```

Troubleshooting layers:

- ALab config/runner errors: inspect the redacted setup log under `.run/logs/`
  and confirm `alab.project.toml` still points to `run:reward.json`.
- Docker daemon or image errors: run `docker version`; Docker availability and
  image pulls/builds are environment prerequisites, not source-code failures.
- Reward parse errors: keep `reward.json` numeric-only. Put diagnostics in
  `summary.md` or another captured artifact.
- uv/dependency errors: the scripts default to
  `UV_DEFAULT_INDEX=https://pypi.org/simple`; check local package-index access
  before treating the example task as failed.

## What It Covers

- Dockerfile runner and Docker image cache behavior;
- `reward.type = "file"` with `run:reward.json`;
- captured manifest/summary/reward artifacts and `artifacts export`;
- exact artifact bytes, with no automatic artifact redaction.
