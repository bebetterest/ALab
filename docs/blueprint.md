# ALab V1 Blueprint

This document is the canonical V1 overview for ALab. Detailed implementation contracts live in the subsystem specs listed below. When a subsystem detail changes, update the matching English spec first and then update the synchronized Chinese `*_cn.md` file in the same change.

## 1. Documentation Map

- CLI, global options, output, command contracts, and errors: [spec_cli.md](spec_cli.md)
- Storage, credentials, auth, context, migrations, and config persistence: [spec_storage_auth_context.md](spec_storage_auth_context.md)
- Project, source, experiment, worktree, run, and submit lifecycle: [spec_project_source_experiment.md](spec_project_source_experiment.md)
- Archive, unarchive, remove, restore, repair, revoke, prune, and lifecycle audit rules: [spec_lifecycle.md](spec_lifecycle.md)
- Runner, reward, log, artifact, Docker, Harbor, and SkyDiscover adapter contracts: [spec_runners_adapters.md](spec_runners_adapters.md)
- Observe, collaboration visibility, logs, tags, artifacts, and annotations: [spec_observe_collaboration.md](spec_observe_collaboration.md)
- Root-only local read-only browser dashboard: [spec_dashboard.md](spec_dashboard.md)
- V1 verification plan and acceptance coverage: [spec_tests.md](spec_tests.md)

Chinese synchronized documents use the same names with `_cn.md`.

## 2. Product Definition

ALab is a local, agent-first Python CLI workbench for iterative experiments. External agents work inside ALab-created Git worktrees. They use `alab` to create attempts, commit iterations, run evaluations, submit final results, inspect visible prior work, export artifacts, write annotations, and leave HOME-level feedback for local suggestions, questions, or bug reports.

ALab owns project structure and local records. It does not launch agents, schedule agents, choose prompts, run search loops, host a remote service, or synchronize data across machines in V1. A root-only local read-only dashboard may be launched by the CLI for loopback browser inspection of the local home.

Core objects:

- Project: task definition, canonical Git repository, source versions, runner configuration, reward policy, mutable path policy, visibility policy, validation records, credentials, and experiments.
- Source: immutable code snapshot imported into a project repository and addressed by `alab/source/<source_id>`.
- Experiment: named attempt with a Git branch, worktree, scoped token, tags, run records, artifacts, annotations, and optional final submission.
- Run: evaluation of a commit with logs, status, reward, metrics, artifacts, runner metadata, and config version.
- Project validation: baseline project-level run proving that the selected source, runner, reward, artifact, environment, timeout, and policy configuration is executable.
- Annotation: revisioned note attached to an experiment, run, artifact, repo path, or repo line range.

V1 is successful when a local user can initialize ALab, create a project, validate the baseline, create experiments from reusable source versions, let agents run and submit without repeatedly entering project keys, and later inspect local history according to explicit collaboration visibility rules.

Project initialization always creates one project admin key when the project record is written and displays that raw admin key exactly once. Root/admin users can inspect sanitized lifecycle audit events through audit commands.

## 3. V1 Boundaries

Out of scope:

- Hosted service, account system, multi-user server, remote web UI, remote database, cloud object storage, or cross-machine sync.
- Built-in LLM provider integration.
- Agent scheduling, autonomous search, or agent hiring.
- Strong local security isolation between users sharing an OS account or filesystem.
- Encrypted SQLite, encrypted record/blob storage, per-record data encryption keys, grant files, public grants, token rewrapping, or encryption-backed revocation.
- Fine-grained OS sandboxing beyond Git scope checks, clean temporary runner directories, and optional Docker execution.
- JSON or XML output. The renderer boundary must allow them later, but V1 exposes only `text` by default and `rich` as a single-command override.
- Arbitrary byte or character span annotations.
- Docker Compose, Kubernetes, or remote container executors.
- Key recovery after a root or admin key is lost.
- Windows host support. V1 officially supports macOS and Linux hosts only.

Security statement:

- V1 authorization is a collaboration boundary for local agent workflows.
- Project data, task text, logs, summaries, feedback, tags, annotations, captured artifacts, and `secret_env` values are stored locally in plaintext SQLite rows or plaintext files.
- ALab must not print raw keys, tokens, or `secret_env` values after creation or input.
- Credential verifiers are stored as salted HMAC hashes, not raw secrets.
- Users who need protection from other local users must rely on OS filesystem permissions or a future encrypted storage mode.

## 4. Runtime And Stack

ALab is installed as a local Python CLI named `alab`.

V1 stack:

- Python 3.11 or newer.
- `uv` for project and dependency management.
- Typer for command routing and argument parsing.
- Rich installed, but never used as the default output path.
- Pydantic for strict model validation.
- Standard-library SQLite for the local index and plaintext records.
- Standard-library `secrets`, `hashlib`, and `hmac` for credential generation and verification.
- `tomli-w` for TOML writing.
- `pathspec` for Git-ignore-style matching.
- pytest for tests.
- Git CLI subprocesses for repository, branch, commit, worktree, and checkout operations.
- Docker CLI as an optional runtime dependency for Docker, Harbor, and SkyDiscover Docker runners.
- Standard-library loopback HTTP serving plus packaged static assets for the root-only read-only dashboard.

Supported hosts are macOS and Linux. Windows is not part of V1 acceptance testing.

Implementation architecture:

- Typer is the CLI boundary only. It parses argv, pre-scans global options, resolves stdin key input, and calls service-layer handlers.
- CLI routing owns a context-aware capability resolver used by `alab`, `alab help`, `alab --help`, nested command help, and command execution preflight. The resolver filters visible and executable commands by current context plus explicit credentials before service handlers run.
- Service-layer handlers own business workflows, lock acquisition, validation sequencing, Git operations, runner orchestration, and lifecycle decisions.
- Repository classes own Python `sqlite3` access through explicit transactions and typed query methods. ALab does not use an ORM in V1.
- Pydantic models validate TOML input, canonical JSON fields, command results, runner records, and renderer input at module boundaries.
- Renderers consume structured result objects. They must not re-query storage, perform authorization checks, or add fields that were not present in the result object.
- The local dashboard uses separate read-model APIs and static assets. Its browser JSON APIs are not CLI output formats and must remain read-only.
- Future implementation should use a layered package shape: CLI routing, service workflows, repositories, Pydantic models, renderers, Git helpers, storage/migrations, runners, adapters, and tests remain separate modules with explicit boundaries.

## 5. ALab Home And Files

Default ALab home:

```text
~/.ALab
```

Home resolution priority:

1. `--home <path>`
2. `ALAB_HOME`
3. `~/.ALab`

Canonical filesystem layout:

```text
~/.ALab/
├── alab.db
├── config.toml
├── backups/
├── project-workspaces/
│   └── <project_id>/
│       └── .alab/
│           └── context.json
├── projects/
│   └── <project_id>/
│       ├── repo.git/
│       └── artifacts/
│           ├── blobs/
│           └── logs/
├── sources/
│   └── skydiscover/
├── cache/
│   ├── docker-images/
│   └── skydiscover-python-envs/
├── feedback/
│   └── <feedback_record>/
│       ├── metadata.json
│       └── body.md
└── tmp/
```

There is no `records/` directory in V1. SQLite is authoritative for structured records. Logs and artifact bytes are file-backed and referenced from SQLite. Agent feedback entries are HOME-level plaintext files under `feedback/`.

`auth init` generates a stable `home_id`, stores it in SQLite, and writes it into every `.alab/context.json` marker. Context repair must verify `home_id` before accepting a marker.

Project workspace directories under `project-workspaces/` are marker-only project control contexts. They are not source checkouts and are never default experiment worktrees. When `exp create` omits `--path`, ALab creates the experiment worktree at `./<project_id>_<exp_id>` relative to the command cwd and registers that resolved path. The cwd may be a project control context, but it is not required to be one; any cwd that passes realpath, emptiness, and nesting checks is valid. Custom experiment and inspection paths may also live outside ALab home when they pass the same checks.

## 6. CLI And Output Summary

Global options may appear before or after subcommands. The CLI must pre-scan global options before context detection, migration, config loading, credential lookup, or command-specific parsing:

```text
alab [--home <path>] [--output text|rich] [--key <secret>] [--key-stdin] <command> [args]
```

`--key` conflicts with `--key-stdin`; `ALAB_KEY` is used only when neither is supplied and the command requires root/admin authorization. Public or optionally authorized commands must not use `ALAB_KEY` to silently elevate output. Global option pre-scan stops at a standalone `--`.

ALab uses a context-aware capability surface. Running `alab`, `alab help`, `alab --help`, or nested command help shows only commands currently available to the caller by default. `alab help --all` may show locked commands with safe reasons and unlock hints. The same resolver gates command execution before command-specific file reads, Git operations, SQLite writes, runner execution, or audit events. Directly invoking a command outside the current surface fails with `COMMAND_UNAVAILABLE` exit `4`; service handlers still perform their normal authorization checks after the preflight passes.

Capability display uses the current context token or public project policy by default. Explicit `--key` or `--key-stdin` unlocks the matching project admin or root surface. `ALAB_KEY` does not affect help or broaden public/token context surfaces, though it may still satisfy root/admin authentication for a command already available in the current context surface.

`text` is the default output and the only persisted output format. It is a strict key-value object format: each object block starts with `object: <type>`, fields render as `field: value`, multiline text renders as an indented block after `field:`, lists render as repeated labeled lines, and repeated objects are separated by one blank line. Warnings render after result blocks as `object: warning`. `rich` uses the same structured result data with different rendering and is available only through `--output rich` for a single command.

`alab dashboard` is a long-running root-only command. It renders a startup `dashboard` object, flushes stdout, starts a temporary `127.0.0.1` HTTP service, and serves packaged static assets plus read-only JSON APIs until shutdown. The dashboard does not change the CLI output contract and must not mutate ALab state.

Every stable error code maps to one numeric exit code. All `*_NOT_FOUND` codes exit `2`; `PROJECT_INVALID` and `COMMAND_UNAVAILABLE` exit `4`; saved runner or validation result errors exit `1`; only failures that cannot store the intended record are system/internal exit `5`.

`ALAB_DEBUG=1` affects internal/system errors only. It may print a full stack trace, but it must not print locals, environment maps, raw keys, raw tokens, secret values, or hidden asset contents.

All ALab object id arguments require complete ids in V1. Git commit selectors are the only values that may use a full or unambiguous abbreviated SHA. Time filter options accept RFC 3339 timestamps with `Z` or an explicit numeric offset and are normalized to UTC `Z` internally.

## 7. Source And Experiment Direction

Sources are immutable Git snapshot refs under `alab/source/<source_id>`. A project may contain many sources, one active project config names exactly one default source, and each experiment binds exactly one source at creation. V1 starts with local path, remote Git, and empty source imports. Git submodules/gitlinks are rejected in V1 with `SOURCE_INVALID`; users must vendor or expand submodule content before import. Harbor and SkyDiscover adapters later materialize source and evaluator inputs through the same source and runner boundaries.

During `project init`, an input config may omit `source.default_source_ref` when the init command supplies exactly one effective default source origin. ALab stages the project repository and source snapshot first, computes the canonical source ref, writes project/source/config/admin credential rows in one SQLite transaction, and prints the raw admin key only after that transaction succeeds. If the input config already contains `source.default_source_ref`, the value is treated as an expected canonical ref; a mismatch with the staged source ref fails with `CONFIG_INVALID` instead of being silently overwritten.

Adapter project init may derive an editable source from a Harbor or SkyDiscover task. If a caller also supplies an explicit editable source, ALab compares the canonical source tree hashes. Identical content dedupes normally. Different content fails with a source conflict, because V1 does not silently choose between two different editable sources during project initialization.

Public no-key experiment creation and public inline source import are enabled by default. Public no-key checkout and observe history are not allowed. Historical observation must happen from an experiment or inspection context with a valid token. Public no-key `exp create --from-exp` is allowed for visible open or closed experiments as a source-inheritance operation, including `final`, `latest`, `best`, and branch-reachable commit SHA selectors. For no-key callers, visibility is the intersection of the current project public inheritance policy and the source experiment's stored visibility upper bound; this prevents public inheritance from bypassing an experiment-level visibility narrowing made when the source experiment was created. Public no-key remote Git imports may use existing non-interactive Git credential helpers, must disable prompts, and must render a stable warning when helpers are available or used. Harbor and SkyDiscover project init do not accept `--source-ref`; new adapter projects use path/Git/empty explicit sources or adapter-derived editable sources.

Project, source, and experiment archive are reversible state changes. Project archive is blocked while active project, validation, source import, run, submit, worktree maintenance, or maintenance locks exist. Each supports unarchive. Archive and unarchive commands are idempotent and do not write duplicate audit events when the target is already in the requested state. Project and experiment unarchive restore the pre-archive status. Permanent removal is a separate audited lifecycle operation defined in [spec_lifecycle.md](spec_lifecycle.md), and hard remove commands support dry-run dependency checks that render blockers without mutating data. Project remove and experiment remove are explicit whole-tree cascade operations after the target itself is archived; source remove remains strict because config versions are immutable reproducibility records.

Experiment worktrees and inspection checkouts are removable by root/admin maintenance commands with dry-run support and trash-staged filesystem deletion. If the registered filesystem path has already been deleted outside ALab, remove commands reconcile the registered state, revoke the token, and write an audit event instead of requiring an impossible repair. Worktree restore checks out the experiment branch HEAD at a supplied path, revokes the old worktree token, and writes a new token to the restored worktree. A marker-only project control context may contain same-project experiment and inspection contexts; cross-project nesting and any nesting inside experiment or inspection contexts are rejected.

## 8. Runner And Adapter Direction

Core V1 is implemented first with local/Git/empty sources and the local runner. Docker, Harbor, and SkyDiscover follow behind the same runner/source adapter contracts.

Adapter decisions:

- Docker runner uses an explicit whitelisted configuration surface: image or dockerfile plus context, network `default|none`, build args, build target, platform, container user, CPU limit, and memory limit. Host networking is not supported in V1 and is not part of the planned Docker surface. Docker rejects Docker Compose, raw Docker argument passthrough, privileged mode, and extra host mounts in V1. Docker-backed runners do not inherit host environment variables; they receive only `[env]`, `[secret_env]`, and ALab internal variables. Missing `runner.image` images are pulled automatically. Dockerfile build contexts follow `.dockerignore`, and cache keys include Dockerfile content, `.dockerignore`, and the effective filtered build context.
- Harbor supports single-step Linux tasks, shared verifier, separate verifier, and safe task-relative `source` imports. It rejects Windows tasks, multi-step tasks, Docker Compose, GPU, MCP, external services, raw Docker passthrough, task-declared host mounts, and placeholder values.
- Harbor separate verifier supports an image or `tests/Dockerfile`; the verifier workspace mount is temporary and writable; hidden verifier logs are admin-only.
- SkyDiscover is evaluator-only in ALab V1. ALab does not run SkyDiscover search loops.
- SkyDiscover source precedence is explicit `--source-*` first; otherwise import the benchmark initial program when present; if absent, init fails and asks for an explicit source. Missing catalogs or missing `skydiscover:<path>` values never trigger automatic network update. Only the initial file or directory is imported.
- SkyDiscover Python evaluator support is part of full V1 through an ALab wrapper subprocess and `uv` environment cache. It is not an OS sandbox. Dependency installation may use the default network, and the environment cache key includes dependency file hashes, platform, and Python version.
- Source-dependent runner paths are checked for safe shape at config time and for existence during baseline/run. Failed runner exits, reward parsing errors, and timeouts still attempt best-effort log and artifact capture when a result record exists.

## 9. Implementation Milestones

Milestone 1: documentation and scaffold.

- Keep this overview and all subsystem specs synchronized in English and Chinese.
- Add README, Chinese README, license, Python project scaffold, no-op CLI skeleton, context-aware help/capability resolver boundary, renderer boundary, and project tooling.

Milestone 2: storage, credentials, and context.

- Implement home resolution, SQLite WAL storage, migrations, backup policy, lifecycle audit events and audit commands, root/admin credentials, experiment tokens, path registry, context markers, context repair, capability-context lookup inputs, secret values, and locks.

Milestone 3: project/source/local runner.

- Implement project init/config/status/validate, local/Git/empty sources, experiment create/archive/unarchive/remove/checkout/worktree maintenance, mutable and visibility policy checks, local runner, exit-code reward, logs, artifacts, run, and submit.

Milestone 4: observe and collaboration records.

- Implement observe commands and aliases, filters, pagination, best ranking, logs, tags, annotations, and artifact export.

Milestone 5: Docker, Harbor, and SkyDiscover.

- Implement Docker runner, Harbor strict subset, SkyDiscover catalog pinning, SkyDiscover Docker evaluator, and SkyDiscover Python evaluator with `uv` environment caching.

## 10. References

Planning references checked on 2026-05-16:

- Git worktree documentation: https://git-scm.com/docs/git-worktree
- Git ignore documentation: https://git-scm.com/docs/gitignore
- Harbor task documentation: https://www.harborframework.com/docs/tasks
- Harbor multi-step task documentation: https://www.harborframework.com/docs/tasks/multi-step
- Harbor Windows task documentation: https://www.harborframework.com/docs/tasks/windows-container-support
- SkyDiscover README and evaluator formats: https://github.com/skydiscover-ai/skydiscover
- uv documentation: https://docs.astral.sh/uv/
- Typer documentation: https://typer.tiangolo.com/
- Pydantic documentation: https://docs.pydantic.dev/latest/
- pathspec package: https://pypi.org/project/pathspec/
- Docker none network driver documentation: https://docs.docker.com/engine/network/drivers/none/
