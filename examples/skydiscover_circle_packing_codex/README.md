# ALab + SkyDiscover Circle Packing + Codex Example Report

This example demonstrates an ALab agent-first workflow: initialize a
SkyDiscover project with ALab, let Codex edit code, run evaluation, and observe
results inside an ALab experiment worktree, then let a Codex controller use the
project admin key to create 3 consecutive experiments and launch workers for
iteration.

The example task is the official SkyDiscover Quick Start
`benchmarks/math/circle_packing` benchmark. The goal is to place 26
non-overlapping circles inside the unit square and maximize the sum of radii.
The official target value is `2.635`; ALab uses the SkyDiscover evaluator's
`combined_score` as the reward.

Official sources:

- SkyDiscover: https://github.com/skydiscover-ai/skydiscover
- Circle Packing benchmark: https://github.com/skydiscover-ai/skydiscover/tree/main/benchmarks/math/circle_packing
- Catalog commit pinned by this example: `c0f6b704a05d883b61eff261023f61897cb45711`

## 1. What This Example Validates

This is not an ALab built-in agent launcher. ALab V1 is still responsible only
for local projects, experiments, runners, records, and visibility; Codex is an
external agent. This example validates how they compose:

- a human initializes the ALab home, SkyDiscover catalog, and project;
- ALab creates an editable source from the SkyDiscover benchmark initial
  program;
- the Codex worker edits only `initial_program.py` inside the ALab worktree;
- the worker calls `alab run` with the worktree token and does not need the
  project key;
- the Codex controller uses the project admin key to create 3 experiments and
  dispatch workers into their directories;
- ALab records the baseline, runs, metrics, reward, logs, and best result;
- `collect_report.sh` generates a small local report at `.run/report.md`.

## 2. Environment Requirements

Run these from the repository root:

```sh
uv run alab help
codex --help
git --version
```

You also need:

- Python 3.11+;
- access to `https://github.com/skydiscover-ai/skydiscover.git`;
- `uv` access to install dependencies for the SkyDiscover Python evaluator;
- a logged-in, working Codex CLI;
- optional `CODEX_MODEL`; when unset, the local Codex default model is used.

Real key handling rules:

- the `root key` is used only for setup and is not written to
  `.run/project.env`;
- the `project admin key` is written to ignored `.run/project.env`;
- the controller uses the project admin key through the `ALAB_PROJECT_KEY`
  environment variable;
- the worker runs with the worktree token, and scripts remove the admin key with
  `env -u ALAB_PROJECT_KEY`;
- README files, reports, and redacted logs do not record real keys.

## 3. Files

```text
examples/skydiscover_circle_packing_codex/
├── alab.project.toml
├── prompts/
│   ├── controller.md
│   └── worker.md
├── scripts/
│   ├── setup_project.sh
│   ├── run_single_worker.sh
│   ├── run_controller.sh
│   └── collect_report.sh
├── README.md
└── README_cn.md
```

Running the example creates ignored `.run/` data:

```text
.run/
├── alab-home/
├── logs/
├── project.env
├── report.md
├── setup-summary.md
├── uv-cache/
└── worktrees/
```

## 4. Project Configuration

Key parts of `alab.project.toml`:

```toml
[mutable]
include = ["initial_program.py"]

[runner]
type = "skydiscover_python"
timeout_seconds = 900
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/math/circle_packing"
program_path = "initial_program.py"

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
```

This configuration lets the agent modify only `initial_program.py`. The
SkyDiscover evaluator still comes from the hidden catalog bundle and is not
exposed to the worker as editable source.

## 5. Initialize the Project

First run a dry-run to inspect paths and commands:

```sh
examples/skydiscover_circle_packing_codex/scripts/setup_project.sh --dry-run
```

Run the real setup:

```sh
examples/skydiscover_circle_packing_codex/scripts/setup_project.sh
```

The script runs:

```sh
alab auth init
alab catalog skydiscover add --commit c0f6b704a05d883b61eff261023f61897cb45711
alab project init skydiscover --config examples/skydiscover_circle_packing_codex/alab.project.toml
```

After initialization succeeds, inspect the project:

```sh
source examples/skydiscover_circle_packing_codex/.run/project.env
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" project show --project \"\$ALAB_PROJECT_ID\""
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" project config show --project \"\$ALAB_PROJECT_ID\""
```

Expected behavior:

- project status is `valid`;
- validation status is `passed`;
- runner type is `skydiscover_python`;
- output warns that the Python evaluator is not an OS sandbox;
- `.run/logs/03-project-init.redacted.log` does not contain the real project
  key.

To rerun from scratch:

```sh
examples/skydiscover_circle_packing_codex/scripts/setup_project.sh --reset
```

## 6. Single Worker Experiment

First run a dry-run:

```sh
examples/skydiscover_circle_packing_codex/scripts/run_single_worker.sh --dry-run
```

Run the real worker:

```sh
examples/skydiscover_circle_packing_codex/scripts/run_single_worker.sh
```

The script will:

1. create the `codex-circle-single` experiment;
2. enter that experiment worktree;
3. launch Codex with `prompts/worker.md`;
4. let the worker edit `initial_program.py`;
5. let the worker run:

```sh
eval "$ALAB_CMD_PREFIX run --message 'codex circle-packing worker improvement'"
```

Inspect the result:

```sh
source examples/skydiscover_circle_packing_codex/.run/project.env
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" runs list --project \"\$ALAB_PROJECT_ID\""
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" exp best --project \"\$ALAB_PROJECT_ID\""
```

## 7. 3-Step Codex Controller Protocol

First run a dry-run:

```sh
examples/skydiscover_circle_packing_codex/scripts/run_controller.sh --dry-run
```

Run the real controller:

```sh
examples/skydiscover_circle_packing_codex/scripts/run_controller.sh
```

The controller uses this fixed protocol:

| Step | Experiment | Source | Worker action | Observe |
|---:|---|---|---|---|
| 1 | `codex-circle-step-1` | project default source | improve `initial_program.py`, run once | inspect run and reward |
| 2 | `codex-circle-step-2` | Step 1 `best` commit | continue from best, run once | compare against Step 1 |
| 3 | `codex-circle-step-3` | Step 2 `best` commit | continue from best, run once | collect final best |

The controller uses the project admin key to create experiments, but worker
child processes do not inherit that key:

```sh
env -u ALAB_PROJECT_KEY \
  ALAB_CMD_PREFIX="$ALAB_CMD_PREFIX" \
  codex exec -C "<worktree>" \
  --add-dir "examples/skydiscover_circle_packing_codex/.run" \
  ${CODEX_MODEL:+-m "$CODEX_MODEL"} \
  --sandbox workspace-write \
  - < examples/skydiscover_circle_packing_codex/prompts/worker.md
```

## 8. Generate the Report

The controller calls the report collector at the end. You can also run it
manually:

```sh
examples/skydiscover_circle_packing_codex/scripts/collect_report.sh
```

Output:

```text
examples/skydiscover_circle_packing_codex/.run/report.md
```

The report includes:

- baseline validation;
- each run's experiment, status, and reward;
- SkyDiscover metrics: `sum_radii`, `target_ratio`, `validity`, `eval_time`;
- best experiment, best run, and best commit;
- command log paths.

Result table template:

| phase | name | status | reward | sum_radii | target_ratio | validity | eval_time | run id | commit |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| baseline | `<validation_id>` | `<passed>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` |  |  |
| run | `codex-circle-step-1` | `<passed/failed/error>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` | `<run_id>` | `<commit>` |
| run | `codex-circle-step-2` | `<passed/failed/error>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` | `<run_id>` | `<commit>` |
| run | `codex-circle-step-3` | `<passed/failed/error>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` | `<run_id>` | `<commit>` |

Do not hand-write or guess results. Before a real run, keep placeholders in the
table; after a real run, treat `.run/report.md` and ALab records as the source
of truth.

Local confirmation snapshot (2026-05-22, single worker flow):

| phase | name | status | reward | sum_radii | target_ratio | validity | eval_time |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | `val-baseline-*` | passed | 0.364237 | 0.959764 | 0.364237 | 1.000000 | 0.201229 |
| run | `codex-circle-single` | passed | 0.998590 | 2.631286 | 0.998590 | 1.000000 | 0.090970 |

That run was produced by a Codex worker that generated a fixed packing in the
experiment worktree, then wrote records into local `.run/alab-home` through the
real SkyDiscover Python evaluator. The exact run id, commit, and log paths are
local and should be read from `.run/report.md`.

## 9. What to Check When Recording Results

Core metrics:

- `combined_score`: ALab reward; higher is better;
- `sum_radii`: sum of the 26 circle radii;
- `target_ratio`: `sum_radii / 2.635`;
- `validity`: whether constraints are satisfied;
- `eval_time`: evaluator runtime.

Judgment criteria:

- whether Step 1 beats the baseline;
- whether Step 2 can continue improving from the Step 1 best commit;
- whether Step 3 continues improving or at least remains valid;
- whether failed/error runs still have explainable logs;
- whether the best result comes from a later step.

## 10. Logs and Troubleshooting

Main logs:

```text
.run/logs/01-auth-init.redacted.log
.run/logs/02-catalog-add.log
.run/logs/03-project-init.redacted.log
.run/logs/single-worker.log
.run/logs/controller.log
.run/logs/report-runs-list.log
.run/logs/report-best.log
```

Common issues:

- `active SkyDiscover catalog not found`: rerun `setup_project.sh`.
- GitHub is unreachable: check network or proxy configuration; catalog clone is
  required.
- Dependency install fails: confirm that `uv` can access the Python package
  index.
- Codex is not logged in: run `codex login` first or repair the local Codex
  configuration.
- `alab help` inside the worker shows `context type: none`: confirm that the
  worker `codex exec` command includes
  `--add-dir examples/skydiscover_circle_packing_codex/.run`; otherwise the
  Codex sandbox can make the ALab home read-only and the context resolver will
  fall back to no context.
- The worker edits files other than `initial_program.py`: ALab mutable scope
  will reject the run.
- The worker prints a key: stop the run, delete `.run/`, rerun setup, and audit
  the prompt/logs.

## 11. Cleanup

Delete all local run data for this example:

```sh
rm -rf examples/skydiscover_circle_packing_codex/.run
```

This does not delete the example files in the repository.
