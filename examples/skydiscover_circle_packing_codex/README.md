# ALab + SkyDiscover Circle Packing + Codex Example Report

This example demonstrates an ALab agent-first workflow: initialize a
SkyDiscover project with ALab, let Codex edit code, run evaluation, and observe
results inside an ALab experiment worktree.

The example task is the official SkyDiscover Quick Start
`benchmarks/math/circle_packing` benchmark. The goal is to place 26
non-overlapping circles inside the unit square and maximize the sum of radii.
The official target value is `2.635`; ALab uses the SkyDiscover evaluator's
`combined_score` as the reward.

## Demo Task

Improve the SkyDiscover circle-packing initial program while preserving the
public `run_packing()` contract. The single-worker script launches one Codex
worker in a token-scoped experiment worktree.

Task shape:

- Editable file: `initial_program.py` imported from the SkyDiscover benchmark.
- Public contract: `run_packing()` must return `(centers, radii, sum_radii)` for
  exactly 26 non-overlapping circles inside the unit square.
- Evaluator: SkyDiscover Python evaluator from the pinned catalog bundle.
- Reward source: SkyDiscover `combined_score`, driven by valid radius sum
  relative to the target value `2.635`.
- Worker boundary: Codex workers edit only the experiment worktree and use the
  worktree token for `alab run`; they do not receive project admin keys.
  ALab home, uv cache, pycache, and `.run/shared` are added only as CLI state
  directories, not as editable source.
- Report output: `collect_report.sh` reads local ALab records and summarizes
  baseline/run metrics into `.run/reports/report.md`.

This example is the most complete demo of external-agent orchestration. It
shows how ALab can record objective evaluation evidence while a separate agent
does the code search inside a constrained worktree.

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
- ALab records the baseline, runs, metrics, reward, logs, and best result;
- `collect_report.sh` generates a small local report at `.run/reports/report.md`.

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
  `.run/secrets/project.env`;
- the `project admin key` is written to ignored `.run/secrets/project.env`;
- the worker runs with the worktree token, and scripts remove the admin key with
  `env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY -u ALAB_KEY`;
- README files, reports, and redacted logs do not record real keys.

## 3. Files

```text
examples/skydiscover_circle_packing_codex/
├── alab.project.toml
├── prompts/
│   └── worker.md
├── scripts/
│   ├── setup_project.sh
│   ├── run_single_worker.sh
│   └── collect_report.sh
├── README.md
└── README_cn.md
```

Running the example creates ignored `.run/` data:

```text
.run/
├── alab-home/
├── logs/
├── reports/
├── secrets/
│   └── project.env
├── shared/
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
source examples/skydiscover_circle_packing_codex/.run/secrets/project.env
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

Before launch, the script refuses unsafe `codex exec -C` paths such as the
repository root, the whole `.run` directory, or `.run/secrets`, runs Codex with
`--sandbox workspace-write`, and checks that added writable side directories are
non-secret CLI state directories.

Inspect the result:

```sh
source examples/skydiscover_circle_packing_codex/.run/secrets/project.env
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" runs list --project \"\$ALAB_PROJECT_ID\""
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" exp best --project \"\$ALAB_PROJECT_ID\""
```

## 7. Generate the Report

Run the report collector after setup or worker runs:

```sh
examples/skydiscover_circle_packing_codex/scripts/collect_report.sh
```

Output:

```text
examples/skydiscover_circle_packing_codex/.run/reports/report.md
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
| run | `codex-circle-single` | `<passed/failed/error>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` | `<run_id>` | `<commit>` |

Do not hand-write or guess results. Before a real run, keep placeholders in the
table; after a real run, treat `.run/reports/report.md` and ALab records as the source
of truth.

Local confirmation snapshot (2026-05-22, single worker flow):

| phase | name | status | reward | sum_radii | target_ratio | validity | eval_time |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | `val-baseline-*` | passed | 0.364237 | 0.959764 | 0.364237 | 1.000000 | 0.201229 |
| run | `codex-circle-single` | passed | 0.998590 | 2.631286 | 0.998590 | 1.000000 | 0.090970 |

That run was produced by a Codex worker that generated a fixed packing in the
experiment worktree, then wrote records into local `.run/alab-home` through the
real SkyDiscover Python evaluator. The exact run id, commit, and log paths are
local and should be read from `.run/reports/report.md`.

## 8. What to Check When Recording Results

Core metrics:

- `combined_score`: ALab reward; higher is better;
- `sum_radii`: sum of the 26 circle radii;
- `target_ratio`: `sum_radii / 2.635`;
- `validity`: whether constraints are satisfied;
- `eval_time`: evaluator runtime.

Judgment criteria:

- whether the worker run beats the baseline;
- whether the worker keeps the circle-packing constraints valid;
- whether failed/error runs still have explainable logs;
- whether the best result is supported by ALab records rather than agent claims.

## 9. Logs and Troubleshooting

Main logs:

```text
.run/logs/01-auth-init.redacted.log
.run/logs/02-catalog-add.log
.run/logs/03-project-init.redacted.log
.run/logs/single-worker.log
.run/logs/report-runs-list.log
.run/logs/report-best.log
```

Common issues:

- ALab setup/config errors: inspect `.run/logs/03-project-init.redacted.log`
  and rerun `setup_project.sh --reset` only when the project state is disposable.
- `active SkyDiscover catalog not found`: rerun `setup_project.sh`.
- GitHub/network errors: check network or proxy configuration; catalog clone is
  required and is separate from ALab runner correctness.
- Dependency install fails: confirm that `uv` can access the Python package
  index. The examples default to `UV_DEFAULT_INDEX=https://pypi.org/simple`.
- Codex is not logged in: run `codex login` first or repair the local Codex
  configuration. Codex login or network failures are external agent runtime
  issues, not ALab evaluator failures.
- `alab help` inside the worker shows `context type: none`: confirm that the
  worker `codex exec` command adds `$ALAB_EXAMPLE_HOME`, `$UV_CACHE_DIR`, and
  `$PYTHONPYCACHEPREFIX`; do not add the whole `.run/` directory or
  `.run/secrets`.
- The worker edits files other than `initial_program.py`: ALab mutable scope
  will reject the run.
- The worker prints a key: stop the run, delete `.run/`, rerun setup, and audit
  the prompt/logs.

## 10. Cleanup

Delete all local run data for this example:

```sh
rm -rf examples/skydiscover_circle_packing_codex/.run
```

This does not delete the example files in the repository.
