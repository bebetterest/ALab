# ALab

<p align="center">
  <img src="docs/assets/readme-header.png" alt="Hand-drawn ALab virtual experiment workbench banner" width="100%">
</p>

> 🤖 Most of the code is completed by [Codex](https://openai.com/codex/).
>
> 📮 Feedback: [bebetterest@outlook.com](mailto:bebetterest@outlook.com)
>
> [English](README.md) | [中文](README_cn.md)

ALab is a local, agent-first Python CLI workbench for iterative experiments. It lets external agents work in isolated Git worktrees, run repeatable evaluations, submit final results, and inspect visible prior experiment evidence through explicit collaboration boundaries.

ALab V1 is intentionally local-only: no hosted service, sync service, remote web UI, built-in agent launcher, or account system. It owns the local project records, source snapshots, experiment lifecycle, runner execution, logs, artifacts, visibility rules, and a root-only local read-only dashboard; agents remain external CLI operators.

## Highlights

- Local CLI workbench for projects, sources, experiments, runs, submissions, logs, artifacts, annotations, and audits.
- HOME-level feedback capture so any ALab role can leave local suggestions, questions, or bug reports without needing project credentials.
- Root-only local dashboard for browser-based read-only inspection of global/project/experiment/run/log/artifact/audit/feedback/system state.
- Markdown evidence reports for project owners or visible experiment contexts through `alab report`.
- Context-aware command surface: `alab help` and command preflight show only what the current project, experiment, inspection checkout, token, or explicit key can use.
- Git-backed experiment isolation: each experiment is an isolated branch/worktree with a worktree token for run and submit operations.
- Reproducible project setup: project config controls runner, reward, artifact capture, environment, secrets, mutable paths, and visibility.
- Runner support for local subprocesses, Docker images/Dockerfiles, Harbor verifiers, and SkyDiscover Python/Docker evaluators.
- Collaboration boundary, not strong local security: root/admin keys and experiment tokens gate CLI capabilities, while local project records remain plaintext.
- Secret hygiene: raw keys/tokens are not stored; generated raw keys are printed once, experiment tokens stay in token files, and `secret_env` values are not rendered or exported.
- Open-source documentation set with English canonical docs and synchronized Chinese `*_cn.md` companions.

## Current Status

The current V1 implementation is runnable and has a closed current-worktree evidence ledger. The product contract remains [docs/blueprint.md](docs/blueprint.md); detailed requirement evidence lives in [docs/completion_audit.md](docs/completion_audit.md); current progress and active queues live in [docs/progress.md](docs/progress.md) and [docs/progress_pipeline.md](docs/progress_pipeline.md).

## Environment Requirements

Required:

- macOS or Linux. Windows is not part of V1 acceptance testing.
- Python 3.11 or newer.
- Git.
- [`uv`](https://docs.astral.sh/uv/) for the project-local Python environment and locked dependency resolution.

Optional:

- Docker, only for Docker runner and Harbor/SkyDiscover Docker evaluator workflows.
- Network access to Python package indexes for dependency-installing evaluator tests.
- Network access to GitHub for live SkyDiscover catalog validation.
- Codex CLI or another external agent runtime if you want autonomous workers; ALab itself does not launch agents.

Local environment variables are documented in [.env.example](.env.example). Real `.env` files are ignored; do not commit root keys, project admin keys, experiment tokens, or secret values.

## Installation

ALab is distributed as the `alab-cli` Python package and installs the `alab` console script. Once the package is published to a Python package index, install it directly with pip:

```sh
python -m pip install alab-cli
alab help
```

Until then, install from a checkout or Git URL:

```sh
python -m pip install "git+https://github.com/bebetterest/ALab.git"
```

Or, from an already cloned checkout:

```sh
git clone https://github.com/bebetterest/ALab.git ALab
cd ALab
python -m pip install .
alab help
```

For editable local development with the installed command:

```sh
python -m pip install -e .
alab help
```

If you prefer an isolated CLI tool environment, `uv` can install the same console script:

```sh
uv tool install --editable .
alab help
```

If `pip` or `uv` installs the command into a directory that is not on `PATH`, add the displayed script directory to your shell path.

For repository development and locked local verification, use the checkout environment instead:

```sh
uv sync --locked
uv run --locked alab help
```

Run the default validation suite:

```sh
uv run --locked pytest -q
uv run --locked ruff check
```

If a local package mirror is slow or unavailable, use the official Python index for the current command:

```sh
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked pytest -q
```

If dependency downloads are unavailable but the current Python environment already has the required test dependencies, the source tree can still be exercised directly:

```sh
PYTHONPATH=src python -m pytest -q
```

## Quick Start

This local runner example creates an isolated ALab home under the repository, initializes a project from a small Python source tree, creates one experiment, runs evaluation, and submits the result.

The commands below assume `alab` is installed. If you are working only from the checkout, replace `alab` with `uv run --locked alab` while inside the repository, or with `uv run --project /absolute/path/to/ALab --locked alab` from an experiment worktree.

Create a demo source and config:

```sh
mkdir -p .alab-demo/source
cat > .alab-demo/source/main.py <<'PY'
print("reward=1.0")
PY

cat > .alab-demo/alab.project.toml <<'TOML'
[runner]
type = "local"
command = ["python", "main.py"]
timeout_seconds = 60
working_directory = "."
env_mode = "sanitized"

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"
TOML
```

Initialize an ALab home. The root key is printed once:

```sh
ALAB_HOME="$PWD/.alab-demo/home" alab auth init
```

Initialize the project with the printed root key:

```sh
ALAB_HOME="$PWD/.alab-demo/home" alab project init local \
  --config .alab-demo/alab.project.toml \
  --source-path .alab-demo/source \
  --name "Demo" \
  --task "Keep the reward output passing" \
  --key <root-key>
```

Create an experiment. Public experiment creation is enabled by default for local agent bootstrap:

```sh
ALAB_HOME="$PWD/.alab-demo/home" alab exp create \
  --project <project-id> \
  --name "attempt-1"
```

Enter the rendered worktree path, run the evaluator, and submit after a passed run:

```sh
cd <worktree-path>
ALAB_HOME="/absolute/path/to/ALab/.alab-demo/home" alab status
ALAB_HOME="/absolute/path/to/ALab/.alab-demo/home" alab run --message "baseline demo run"
ALAB_HOME="/absolute/path/to/ALab/.alab-demo/home" alab submit \
  --message "final demo candidate" \
  --summary "The demo candidate prints a parseable reward." \
  --feedback "The latest run passed with reward 1.0." \
  --ref none
```

For projects configured with `runner.type = "none"` and `reward.type = "none"`,
there is no evaluator. In that free evaluation mode, skip `alab run` and submit
directly; the submission records `final run id: none` and is excluded from best
reward ranking.

Useful next commands:

```sh
alab help
alab feedback --kind suggestion --body "Describe a suggestion, question, or bug for the project owner."
alab --key <root-key> feedback list
alab --key <root-key> dashboard --no-open
alab --key <admin-or-root-key> report --project <project-id> --out ./alab-project-report.md
alab observe experiments list
alab observe runs list --exp <exp-id>
alab observe experiments best
```

## Core Concepts

- **Home**: local ALab state root containing SQLite records, config, caches, backups, and project storage.
- **Project**: task, goal, config, source registry, validation records, visibility policy, and project admin boundary.
- **Source**: immutable snapshot imported from a local path, Git repo, empty source, Harbor task source, or SkyDiscover initial program.
- **Experiment**: isolated Git branch/worktree bound to exactly one source and one config version.
- **Run**: one evaluator execution for an experiment commit, with status, reward, logs, artifacts, and warning codes.
- **Submit**: closes an experiment with final summary, feedback, final commit, explicit refs, and either a final run or `final run id: none` for free evaluation projects.
- **Feedback**: HOME-level plaintext notes for suggestions, questions, bugs, or other agent observations, stored as one directory per entry under `feedback/`. Any initialized-home role can submit feedback; root can list, show, and archive records without creating SQLite or audit rows.
- **Dashboard**: root-only local browser panel for read-only inspection. It binds to `127.0.0.1`, uses a random browser session token, serves bounded paginated read models for large homes, and writes no ALab records.
- **Reports**: Markdown evidence exports for project-level owner handoffs or visible experiment contexts, without raw secrets, hidden log contents, or artifact bytes.
- **Inspection checkout**: read-only checkout for observing/exporting scoped experiment evidence without becoming submit-capable.

## Configuration

Project behavior is controlled by TOML config:

- `[runner]`: runner type, command/shell, working directory, timeout, Docker fields, Harbor task refs, SkyDiscover task refs, or `type = "none"` for free evaluation.
- `[reward]`: reward type and primary metric. Supported reward families include `exit_code`, `file`, `stdout_regex`, `harbor`, `skydiscover`, and `none`. `reward.type = "none"` must be paired with `runner.type = "none"`.
- `[artifacts]` and `[logs]`: captured output roots, glob patterns, and byte limits.
- `[env]` and `[secret_env]`: explicit environment injection. Secret values are local plaintext but are not rendered or exported.
- `[mutable]`: paths the experiment may change when running or submitting.
- Visibility/public bootstrap policy: controls how experiments can see prior work and whether local no-key experiment creation is allowed.

See [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md), [docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md), and [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md) for the detailed contracts.

## Examples

See [examples](examples/) for the runnable example matrix. The current examples
cover a free-evaluation static introduction site with manual review, a local
scoring loop, a Dockerized clinic-order fulfillment planner with artifact
export, a Harbor hidden-verifier incident classifier, a collaborative incident
triage lifecycle workflow, a generated dashboard showcase home, and the
SkyDiscover circle-packing Codex single-worker protocol. The same examples area also includes
`examples/templates/`, a copyable multi-instance TSP template library for
local, Docker, Harbor, SkyDiscover Python, and SkyDiscover Docker runner
projects.

The repository also includes Codex-facing role skills under [skills](skills/). They are external runbooks for operating ALab through the CLI as an experiment worker, project controller, or global admin; they do not add an embedded agent launcher to ALab.

## Testing And Development

Default checks:

```sh
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked pytest -q
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked ruff check
```

Opt-in integration gates are excluded from the default suite:

```sh
ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m real_docker
ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m real_skydiscover_python
ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m networked_skydiscover_python
ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m native_skydiscover_python
ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m live_skydiscover_catalog
```

Notes:

- `uv.lock` is tracked because CI and local validation use `uv run --locked`.
- Keep local cache/output paths ignored (`.uv-cache/`, `.pytest_cache/`, `.ruff_cache/`, `.alab-demo/`, `.env`).
- GitHub Actions runs the default lint and pytest suite on pull requests and pushes to `main`; real Docker and live/networked SkyDiscover gates remain manual workflow inputs.
- Pushes to `main` check PyPI for the current `pyproject.toml` package version; if that exact version is missing, CI builds and publishes through PyPI Trusted Publishing, then creates a `v<version>` GitHub Release from the matching [CHANGELOG.md](CHANGELOG.md) section. If PyPI already has that version, publishing and release creation are skipped.
- The PyPI `alab-cli` project must trust repository `bebetterest/ALab`, workflow `ci.yml`, and environment `pypi` before the first automated publish can succeed.

## Security And Data Model

ALab V1 is a local collaboration boundary, not a multi-user security product:

- Raw root/admin keys are printed only at creation/regeneration.
- Raw experiment tokens are written to token files and are not printed.
- Credential verifiers are stored; raw credential secrets are not.
- Project records are local plaintext SQLite/filesystem data.
- `secret_env` values are local plaintext, redacted from rendered logs where configured, and never exported by config commands.
- The dashboard is loopback-only and root-only. Its API can read hidden/full logs and artifact bytes for that root session, but it must not render raw keys, raw tokens, credential verifier material, or raw `secret_env` values.
- Artifact exports are exact captured bytes and are not automatically redacted.

## Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── assets/
│   │   └── readme-header.png
│   ├── README.md
│   ├── README_cn.md
│   ├── blueprint.md
│   ├── blueprint_cn.md
│   ├── completion_audit.md
│   ├── completion_audit_cn.md
│   ├── progress.md
│   ├── progress_cn.md
│   ├── progress_pipeline.md
│   └── progress_pipeline_cn.md
├── examples/
│   ├── README.md
│   ├── README_cn.md
│   ├── collaboration_observe_lifecycle/
│   ├── dashboard_showcase/
│   ├── docker_file_reward_artifacts/
│   ├── free_evaluation_intro_site/
│   ├── harbor_verifier_minimal/
│   ├── local_agent_scoreboard/
│   ├── skydiscover_circle_packing_codex/
│   └── templates/
├── skills/
│   ├── alab-experiment-worker/
│   ├── alab-project-controller/
│   └── alab-global-admin/
├── src/
│   └── alab/
├── tests/
│   ├── test_smoke.py
│   ├── test_cli_contract.py
│   ├── test_runner_docker.py
│   ├── test_runner_harbor.py
│   └── test_runner_skydiscover.py
├── LICENSE
├── .env.example
├── CHANGELOG.md
├── CHANGELOG_cn.md
├── pyproject.toml
├── uv.lock
├── README.md
└── README_cn.md
```

Local-only agent notes such as `AGENTS.md` and `CORE.md` are intentionally git-ignored and are not part of the public repository layout.

## Documentation

- English documentation is canonical.
- Synchronized Chinese documents use the `*_cn.md` naming pattern.
- [docs/README.md](docs/README.md) explains the documentation structure and reading order.
- [docs/blueprint.md](docs/blueprint.md) is the V1 product overview.
- [docs/spec_cli.md](docs/spec_cli.md), [docs/spec_storage_auth_context.md](docs/spec_storage_auth_context.md), [docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md), [docs/spec_lifecycle.md](docs/spec_lifecycle.md), [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md), [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md), [docs/spec_dashboard.md](docs/spec_dashboard.md), and [docs/spec_tests.md](docs/spec_tests.md) define subsystem contracts.
- [docs/progress.md](docs/progress.md), [docs/progress_pipeline.md](docs/progress_pipeline.md), [docs/progress_closed_gaps.md](docs/progress_closed_gaps.md), and [docs/progress_log.md](docs/progress_log.md) track current state, active queues, closed gaps, and history.
- [docs/completion_audit.md](docs/completion_audit.md) tracks requirement-level evidence.
- [CHANGELOG.md](CHANGELOG.md) records release-facing changes and is used by CI for GitHub Release notes.

## Contributing

- Keep changes scoped and aligned with the blueprint/spec contracts.
- Update English docs first, then synchronize the matching Chinese `*_cn.md` file.
- Add focused tests for new behavior and run the relevant pytest/ruff commands before opening a PR.
- Do not commit real `.env` files, raw keys, experiment tokens, generated caches, local ALab homes, or private runner outputs.

## License

The project license is `GPL-3.0-or-later`; see [LICENSE](LICENSE).
