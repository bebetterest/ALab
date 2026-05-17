# ALab

ALab is a local, agent-first Python CLI workbench for iterative experiments. It is designed for workflows where external agents work inside ALab-created Git worktrees, run evaluations, submit final results, and inspect prior experiment history through explicit collaboration visibility rules.

The project is currently in blueprint phase. No runnable CLI, package scaffold, or dependency environment is implemented yet. The canonical overview is [docs/blueprint.md](docs/blueprint.md), with synchronized subsystem specs under `docs/` and Chinese versions using the `*_cn.md` pattern.

## Highlights

- Local-only V1: no server, sync service, web UI, built-in agent launcher, or account system.
- Agent-first CLI: default and persisted output is plain text; Rich output is available only per command with `--output rich`.
- Context-aware command surface: `alab`, `alab help`, and command preflight show and allow only commands available for the current project, experiment, inspection context, and explicit key.
- Collaboration boundary, not strong local security: root/admin keys and experiment tokens guide CLI permissions, while project records are local plaintext data.
- Secret hygiene: raw keys/tokens are not stored, `secret_env` values are local plaintext but not rendered or exported, and configured secrets are redacted from logs. Artifact exports are exact captured bytes and are not automatically redacted.
- Project/experiment model: projects define task, source, runner, reward, artifacts, mutable scope, and visibility; experiments are isolated Git branches and worktrees.
- Immutable source snapshots: local, Git, empty, Harbor, and SkyDiscover inputs are represented as source refs in a canonical project repository.
- Multi-source projects: a project may retain many sources, each active config has one default source, and every experiment binds exactly one source when it is created.
- Staged implementation: the core milestone focuses on local/Git/empty sources and the local runner; Docker, Harbor, and SkyDiscover follow as first-class V1 adapters.
- Implementation model: the planned stack is Typer CLI handlers over service workflows, explicit `sqlite3` repositories, Pydantic boundary models, and renderer-only command result objects.
- Baseline validation: project init and runtime-affecting config changes run a baseline test by default.
- Public bootstrap: projects default to local no-key experiment creation from sources or visible open/closed experiments for agent convenience, with public from-experiment inheritance capped by the source experiment visibility bound and without granting project-management or observe-history access.
- Inspection checkouts: read-only CLI contexts can observe/export with scoped tokens without becoming submit-capable experiments.
- Explicit lifecycle model: archive/unarchive are idempotent reversible states, remove is audited archive-first deletion with dry-run blockers, worktree remove can reconcile already-missing registered paths, and prune/gc only clean non-authoritative data.
- Runner plan: local, explicit-field Docker with `default|none` networking only, Harbor strict single-step Linux subset, SkyDiscover Docker evaluator, and SkyDiscover Python evaluator contracts are specified for V1.

## Planned Usage

The final CLI is expected to look like this:

```text
alab auth init
alab project init local --config alab.project.toml --source-path . \
  --name "Example" --task "Fix the project" --key <root-key>
alab project validate --project <project_id> --key <root-or-admin-key>
alab exp create --project <project_id> --name "attempt-1"
cd ./<project_id>_<exp_id>
alab status
alab help
alab run --message "try first fix"
alab submit --message "final" --summary "..." --feedback "..." --ref none
```

All runner, reward, artifact, log, environment, and secret settings are expected to come from the project config file. These commands are design targets, not currently executable commands. Project initialization is expected to print one generated project admin key exactly once after the project record is written.

The planned CLI help is context-aware. In an experiment worktree with only its token, `alab help` should focus on status, run, submit, visible observe, tags, annotations, and own-experiment record maintenance. Project and root management commands are hidden by default and direct attempts to use unavailable commands fail before side effects with `COMMAND_UNAVAILABLE`. Explicit `--key` or `--key-stdin` unlocks the matching admin/root surface; ambient `ALAB_KEY` does not expand help or token/public command surfaces.

## Repository Structure

```text
.
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
│   └── spec_tests_cn.md
├── README.md
└── README_cn.md
```

Local-only agent notes such as `AGENTS.md` and `CORE.md` are intentionally git-ignored and are not part of the public repository layout.

Future implementation is expected to add `src/alab/`, `tests/`, `pyproject.toml`, and `LICENSE`.

## Development Workflow

Until implementation starts, development work should focus on keeping the blueprint decision-complete and synchronized. When implementation begins, use the project-local environment and pinned dependencies, keep CLI rendering separate from command logic, keep SQLite access behind explicit repository classes, and add focused unit and integration tests for every major workflow.

The first implementation milestone should make the local workflow usable before adding heavier adapters: scaffold the CLI, implement storage/credentials/context, support local/Git/empty source import, run the local runner, and complete run/submit/observe basics. Docker, Harbor, and SkyDiscover should then land behind the runner/source adapter interfaces already defined in the blueprint.

## Documentation

- English documentation is canonical.
- Synchronized Chinese documents use the `*_cn.md` naming pattern.
- Keep [docs/blueprint.md](docs/blueprint.md) as the overview.
- Keep subsystem specs synchronized with their Chinese counterparts:
  - [docs/spec_cli.md](docs/spec_cli.md)
  - [docs/spec_lifecycle.md](docs/spec_lifecycle.md)
  - [docs/spec_storage_auth_context.md](docs/spec_storage_auth_context.md)
  - [docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md)
  - [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md)
  - [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md)
  - [docs/spec_tests.md](docs/spec_tests.md)

## License

The planned project license is `GPL-3.0-or-later`. The license file has not been added yet.
