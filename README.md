# ALab

ALab is a local, agent-first Python CLI workbench for iterative experiments. It is designed for workflows where external agents work inside ALab-created Git worktrees, run evaluations, submit final results, and inspect prior experiment history through explicit collaboration visibility rules.

The project now has runnable local workflow milestones. The canonical V1 product contract remains [docs/blueprint.md](docs/blueprint.md), with synchronized subsystem specs under `docs/` and Chinese versions using the `*_cn.md` pattern.

## Highlights

- Local-only V1: no server, sync service, web UI, built-in agent launcher, or account system.
- Agent-first CLI: default and persisted output is plain text; Rich output is available only per command with `--output rich`.
- Context-aware command surface: `alab`, `alab help`, and command preflight show and allow only commands available for the current project, experiment, inspection context, and explicit key.
- Collaboration boundary, not strong local security: root/admin keys and experiment tokens guide CLI permissions, while project records are local plaintext data.
- Secret hygiene: raw keys/tokens are not stored, `secret_env` values are local plaintext but not rendered or exported, and configured secrets are redacted from logs. Artifact exports are exact captured bytes and are not automatically redacted.
- Project/experiment model: projects define task, source, runner, reward, artifacts, mutable scope, and visibility; experiments are isolated Git branches and worktrees.
- Immutable source snapshots: local, Git, empty, Harbor task sources, and SkyDiscover initial programs are represented as source refs in a canonical project repository.
- Multi-source projects: a project may retain many sources, each active config has one default source, and every experiment binds exactly one source when it is created.
- Staged implementation: the core milestone makes local/Git/empty sources and the local runner usable; Docker image/Dockerfile configs, Harbor verifiers, and SkyDiscover Python/Docker evaluators now execute behind the same runner contract.
- Implementation model: the current scaffold provides a Python CLI entry point, explicit `sqlite3` storage, Pydantic config boundary models, and renderer-only command result objects. The command registry is in place for the V1 surface, with later commands registered behind implementation boundaries.
- Baseline validation: project init and runtime-affecting config changes run a baseline test by default.
- Public bootstrap: projects default to local no-key experiment creation from existing sources, inline source imports, or visible open/closed experiments for agent convenience, with public from-experiment inheritance capped by the source experiment visibility bound and without granting project-management or observe-history access.
- Inspection checkouts: read-only CLI contexts can observe/export with scoped tokens without becoming submit-capable experiments.
- Explicit lifecycle model: archive/unarchive are idempotent reversible states, remove is audited archive-first deletion with dry-run blockers, worktree/inspection and dependent run/validation artifact/log removals stage filesystem paths through ALab trash with reference counting, and prune/gc only clean non-authoritative data.
- Runner plan: the local runner is implemented; Docker supports explicit image/Dockerfile execution with `default|none` networking, host workspace/run mounts, `.dockerignore`-aware build cache keys, auto-pull for missing images, runtime capability cache refresh, and ALab-owned image cache pruning; Harbor verifiers and SkyDiscover Python/Docker evaluators now materialize hidden bundles and store raw verifier/evaluator output as hidden logs.

## Current Status

Implemented in the first runnable milestone:

- Package scaffold with `pyproject.toml`, `src/alab/`, tests, and `alab` entry point.
- Strict text object rendering, stable error object rendering, global option pre-scan, context-aware help, and command preflight.
- ALAB home initialization, file-backed SQLite migration loading with checksum validation and pre-upgrade backups, SQLite WAL schema, root/admin/token verifier storage, project control context markers, experiment token files, path registry records with case-normalized hashing on case-insensitive filesystems, and `context show/repair` with self-token Git branch/pinned-commit checks.
- Local project initialization from local/Git/empty source origins, canonical source refs, baseline validation, local runner execution, log/artifact storage, experiment worktree creation, run, submit, status/list, observe runs/logs/artifacts, and audit list/show.
- Root/admin key create/list/revoke, project config show/export/import/set, project env set/unset/list, project secret set/unset/list/gc with non-rendered raw secret values, manual project validation, validation archive/unarchive/remove, stale lock clearing, backup prune, and cache prune.
- Post-init source import/show/list/archive/unarchive/remove dry-run, Git-aware local source filtering for tracked/untracked files, `.gitignore`, `.alabignore`, built-in sensitive excludes, and empty-filter warnings, experiment archive/unarchive/remove dry-run, project archive/unarchive/remove dry-run, and experiment tag add/remove/list.
- Experiment worktree remove/restore, experiment token list/revoke/regenerate, inspection checkout/create/remove, trash-staged worktree/inspection filesystem removal with missing-path reconciliation, experiment remove cascade staging for branch refs/worktree/inspection/log/artifact paths, standalone artifact/log remove with reference-counted trash staging, `run remove --cascade` for dependent artifact/log rows with latest/final-run metadata, validation remove with dependent artifact/log reference-counted trash staging, project whole-tree remove cascade staging for project roots/control paths/registered worktrees/inspection checkouts, retained revoked token/path rows, trash cache pruning, annotation add/edit/archive/unarchive/remove with revision-count remove audit, Git-backed path/line target validation, and observe annotations list/show, documented observe filters and sort whitelists for experiment/run/artifact/log/annotation list surfaces, public `--from-exp` experiment creation capped by source experiment visibility, public inline source import for `exp create --source-*` with project policy limits and public `--source-git` credential-helper warnings, and experiment observe list/search/show/best with same-project/explicit token visibility plus best incomparable-run warnings.
- Docker runner execution for explicit `runner.image` and `runner.dockerfile` configs, including container-visible ALab env values, `default|none` network selection, Dockerfile cache key computation, runtime capability cache refresh, per-architecture platform capability checks for `linux/amd64` and `linux/arm64`, pre-write rejection for unsupported configured platform/resource limits, ALab-owned image tag pruning, and fake-Docker contract tests that do not require a daemon.
- SkyDiscover catalog add/update/show/remove with exact commit pinning, local Git cleanliness checks, safe `skydiscover:<path>` ref resolution for configured tasks/evaluators, active-reference blockers, and no-network show.
- SkyDiscover Python evaluator execution through a subprocess wrapper, hidden evaluator bundle staging, hidden evaluator stdout/stderr logs, structured metric/reward capture, and ALab-managed `uv` environment cache rows that `cache prune --skydiscover-envs` can remove.
- SkyDiscover Docker evaluator execution through hidden bundle staging, Docker image build cache rows, read-only evaluator bundle mounts separate from candidate workspaces, stdout JSON metric parsing, feedback-only evaluator artifacts JSON, and hidden evaluator stdout/stderr logs.
- Harbor strict single-step verifier execution for shared environment images/Dockerfiles and separate verifier images/`tests/Dockerfile`, including strict unsupported-field rejection, literal task environment values treated as secrets, hidden verifier bundle staging, hidden verifier logs, reward file parsing from `run:/logs/verifier/reward.{txt,json}`, and Docker image cache rows for verifier Dockerfiles.
- Harbor/SkyDiscover adapter-derived editable-source bootstrap: Harbor imports only supported task `source` paths or falls back to empty source, can use `instruction.md` when project task text is otherwise empty, SkyDiscover imports only benchmark initial program files/directories, and explicit caller sources are tree-hash checked against adapter-derived sources before deduping.
- V1 command registry coverage for the documented command surface; commands outside this milestone fail explicitly before accidental side effects.

## Usage

```text
alab auth init
alab project init local --config alab.project.toml --source-path . \
  --name "Example" --task "Fix the project" --key <root-key>
alab exp create --project <project_id> --name "attempt-1"
cd ./<project_id>_<exp_id>
alab status
alab help
alab run --message "try first fix"
alab submit --message "final" --summary "..." --feedback "..." --ref none
```

All runner, reward, artifact, log, environment, and secret settings come from the project config file. Project initialization prints one generated project admin key exactly once after the project record is written.

The CLI help is context-aware. In an experiment worktree with only its token, `alab help` focuses on the currently available surface. Project and root management commands are hidden by default and direct attempts to use unavailable commands fail before side effects with `COMMAND_UNAVAILABLE`. Explicit `--key` or `--key-stdin` unlocks the matching admin/root surface; ambient `ALAB_KEY` does not expand help or token/public command surfaces.

The repository also includes Codex-facing role skills under `skills/`. They are external runbooks for operating ALab through the CLI as an experiment worker, project controller, or global admin; they do not add an embedded agent launcher to ALab.

## Setup

Install and run through `uv`:

```text
uv run alab help
uv run pytest
```

If a local mirror is slow or unavailable, use the official PyPI index for the current command and keep the cache inside the repository:

```text
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest
```

When dependency downloads are unavailable, the current tests can also be run with an existing Python environment that already has pytest and pydantic:

```text
PYTHONPATH=src python -m pytest
```

Optional local environment variables are listed in `.env.example`. Real `.env` files are ignored; keep actual root/admin keys, experiment tokens, and `secret_env` values out of tracked files.

Real Docker-backed integration coverage is opt-in so the default suite never pulls images unexpectedly. It covers Docker image command and shell runners, real container environment isolation with internal `ALAB_*` override precedence, Dockerfile build-context filtering and cache reuse, Harbor verifier execution with task/external secret injection, SkyDiscover Docker evaluator execution with secret injection, and real Docker image-cache reuse for Dockerfile-backed adapter images when Docker is available:

```text
ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m real_docker
```

Real SkyDiscover Python dependency-installation coverage is also opt-in. It creates a real `uv` evaluator environment and installs a locally generated wheel, so it exercises the dependency path without requiring network access:

```text
ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache uv run pytest -m real_skydiscover_python
```

Networked SkyDiscover Python dependency coverage is a separate opt-in path. It installs direct and transitive pure-Python dependency cases from the configured Python index through the evaluator environment:

```text
ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m networked_skydiscover_python
```

Native/binary SkyDiscover Python dependency coverage is separately opt-in. It defaults to installing `orjson>=3.10,<4` from the configured Python index and can be overridden with `ALAB_NATIVE_SKYDISCOVER_PYTHON_REQUIREMENT` plus `ALAB_NATIVE_SKYDISCOVER_PYTHON_MODULE`:

```text
ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m native_skydiscover_python
```

Live SkyDiscover catalog coverage is opt-in because it clones the official catalog from the network. It verifies exact commit pinning, no-network `catalog show`, and resolving a real catalog evaluator through `project init skydiscover --skip-baseline-test`:

```text
ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=.uv-cache uv run pytest -m live_skydiscover_catalog
```

Lint the current code with:

```text
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check
```

GitHub Actions runs the default lint and pytest suite on pull requests and pushes to `main`. The workflow splits the default pytest suite into file groups so the slow CLI contract and smoke suites can run in parallel; real Docker, SkyDiscover Python dependency, and live catalog gates remain manual `workflow_dispatch` inputs.

## Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── blueprint.md
│   ├── blueprint_cn.md
│   ├── spec_cli.md
│   ├── spec_cli_cn.md
│   ├── spec_lifecycle.md
│   ├── spec_lifecycle_cn.md
│   ├── spec_storage_auth_context.md
│   ├── spec_storage_auth_context_cn.md
│   ├── spec_project_source_experiment.md
│   ├── spec_project_source_experiment_cn.md
│   ├── spec_runners_adapters.md
│   ├── spec_runners_adapters_cn.md
│   ├── spec_observe_collaboration.md
│   ├── spec_observe_collaboration_cn.md
│   ├── spec_tests.md
│   ├── spec_tests_cn.md
│   ├── completion_audit.md
│   ├── completion_audit_cn.md
│   ├── progress.md
│   ├── progress_cn.md
│   ├── progress_pipeline.md
│   ├── progress_pipeline_cn.md
│   ├── progress_closed_gaps.md
│   ├── progress_closed_gaps_cn.md
│   ├── progress_log.md
│   └── progress_log_cn.md
├── examples/
│   └── skydiscover_circle_packing_codex/
├── skills/
│   ├── alab-experiment-worker/
│   ├── alab-project-controller/
│   └── alab-global-admin/
├── src/
│   └── alab/
├── tests/
│   ├── test_smoke.py
│   ├── test_runner_docker.py
│   ├── test_runner_harbor.py
│   └── test_runner_skydiscover.py
├── LICENSE
├── .env.example
├── pyproject.toml
├── README.md
└── README_cn.md
```

Local-only agent notes such as `AGENTS.md` and `CORE.md` are intentionally git-ignored and are not part of the public repository layout.

## Development Workflow

Use the project-local environment and pinned dependencies where available. Keep CLI rendering separate from command logic, keep SQLite access behind explicit repository helpers, and add focused unit and integration tests for every major workflow.

The first implementation milestone makes the local workflow usable before adding heavier adapters: scaffold the CLI, implement storage/credentials/context, support local/Git/empty source import, run the local runner, and complete run/submit/observe basics. Docker, Harbor, SkyDiscover Python/Docker, and adapter-derived editable-source bootstrap now land behind the same source/runner boundaries.

## Documentation

- English documentation is canonical.
- Synchronized Chinese documents use the `*_cn.md` naming pattern.
- Keep [docs/blueprint.md](docs/blueprint.md) as the overview.
- Track the current implementation dashboard in [docs/progress.md](docs/progress.md).
- Track the active implementation queue in [docs/progress_pipeline.md](docs/progress_pipeline.md).
- Keep duplicate-work guardrails in [docs/progress_closed_gaps.md](docs/progress_closed_gaps.md).
- Keep the historical implementation journal in [docs/progress_log.md](docs/progress_log.md).
- Track requirement-level completion evidence in [docs/completion_audit.md](docs/completion_audit.md).
- Keep subsystem specs synchronized with their Chinese counterparts:
  - [docs/spec_cli.md](docs/spec_cli.md)
  - [docs/spec_lifecycle.md](docs/spec_lifecycle.md)
  - [docs/spec_storage_auth_context.md](docs/spec_storage_auth_context.md)
  - [docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md)
  - [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md)
  - [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md)
  - [docs/spec_tests.md](docs/spec_tests.md)

## License

The project license is `GPL-3.0-or-later`; see [LICENSE](LICENSE).
