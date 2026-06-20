# ALab V1 Project, Source, Experiment, Run, And Submit Spec

This spec defines project config, source import, experiment creation, run lifecycle, and submit lifecycle. Cross-object archive, unarchive, remove, restore, and audit semantics are defined in [spec_lifecycle.md](spec_lifecycle.md).

## 1. Project Config Schema

Project definitions are imported/exported as TOML and stored as canonical JSON.

Minimal TOML:

```toml
schema_version = 1

[project]
name = "Example Project"
goal = "Optional high-level goal"
task = "Task text"
allow_public_exp_create = true

[source]
default_source_ref = "alab/source/src-base-abc123"

[public_source_import]
enabled = true
max_files = 100000
max_total_bytes = 1073741824
max_file_bytes = 104857600

[mutable]
include = ["**"]
exclude = []

[visibility]
scope = "same_project"
experiment_ids = []

[metrics]
reference = [
  { name = "latency_ms", label = "Latency", direction = "minimize", unit = "ms" },
  { name = "coverage", label = "Coverage", direction = "maximize" },
]

[runner]
type = "local"
timeout_seconds = 600
working_directory = "."
env_mode = "sanitized"
command = ["uv", "run", "pytest"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = []
per_file_limit_bytes = 10485760
per_run_limit_bytes = 104857600

[logs]
stdout_limit_bytes = 10485760
stderr_limit_bytes = 10485760

[git]
author_name = "ALab"
author_email = "alab@local"

[env]
PYTHONUNBUFFERED = "1"

[secret_env]
# TOKEN = "..."
```

Field rules:

- `schema_version` must be `1`.
- `project.name` and `project.task` are required non-empty strings.
- `project.goal` is optional.
- `project.allow_public_exp_create` defaults to `true`.
- Project, source, and experiment display names are limited to 120 bytes after UTF-8 encoding.
- Names are unique within scope by normalized slug, not exact string.
- Task, goal, summary, feedback, and annotation body values are each limited to 65536 bytes after UTF-8 encoding. Annotation titles are limited to 256 bytes after UTF-8 encoding.
- A project may contain many source records. Stored canonical project configs contain one `source.default_source_ref`, and it must resolve to an active source before new experiments are created.
- Each experiment binds exactly one source at creation. If `exp create` does not select a source or `--from-exp`, ALab uses the active config's `source.default_source_ref`.
- Project init input configs may omit `source.default_source_ref` when the init command supplies exactly one effective default source origin. ALab stages that source first, injects its canonical `alab/source/<source_id>` ref into the stored config, and then validates the full canonical config.
- If a project init input config includes `source.default_source_ref`, the value is an expected canonical source ref. If it differs from the staged canonical source ref, init fails with `CONFIG_INVALID`; ALab must not silently overwrite it.
- `project.allow_public_exp_create` and `public_source_import.enabled` are strict booleans.
- `public_source_import.enabled` defaults to `true`.
- Public source import limits default to the normal source limits and are project-configurable. V1 has no separate hard-coded cap.
- `public_source_import.max_files`, `public_source_import.max_total_bytes`, and `public_source_import.max_file_bytes` must be non-negative integers.
- Public callers may not override public import limits upward at command time.
- `mutable.include` defaults to `["**"]` and must contain at least one non-empty single-line pattern; `mutable.exclude` defaults to `[]` and, when set, contains non-empty single-line patterns.
- `visibility.scope` is `none`, `same_project`, or `explicit`.
- `visibility.experiment_ids` is required and non-empty only when `scope = "explicit"`; entries must be complete experiment ids and are normalized to a sorted unique list.
- `metrics.reference` defaults to `[]` and declares optional numeric run metrics that the dashboard may plot as reference curves. Each entry has `name`, optional `label`, `direction = "maximize"|"minimize"`, and optional `unit`.
- `metrics.reference[].name` must match `^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$` and must be unique within the project config.
- Reference metrics are display metadata only. They do not change reward parsing, best ranking, submit behavior, or run status. Actual values are optional per run and come from the run record's numeric `metrics` map.
- `runner.type` is `none`, `local`, `docker`, `harbor`, `skydiscover_docker`, or `skydiscover_python`.
- `runner.type = "none"` enables free evaluation mode and must be paired with `reward.type = "none"`. It rejects executable runner fields such as commands, shell, Docker fields, Harbor refs, and SkyDiscover refs.
- `runner.timeout_seconds` defaults to `600` and must be an integer between `1` and `86400`.
- `runner.working_directory` is repo-relative and must not escape the repository.
- `runner.env_mode` is valid only for local runner and is `sanitized`, `full`, or `none`.
- `runner.network` is valid for Docker-backed runners and is `default` or `none`; it defaults to `default`.
- Docker host networking is not supported in V1. `runner.network = "host"` fails config validation with `CONFIG_INVALID`.
- `runner.command` is non-empty argv list mode when provided; `runner.shell` is non-empty explicit shell mode when provided; they conflict. `runner.shell` is valid only for the local runner and Docker runner shell mode in V1. Harbor and SkyDiscover adapters own their verifier/evaluator commands and reject user `runner.shell`.
- Docker runner requires exactly one of `runner.image` or `runner.dockerfile`.
- Dockerfile runner requires `runner.context`.
- Docker runner may set whitelisted Docker fields: `runner.build_args`, `runner.target`, `runner.platform`, `runner.user`, `runner.cpus`, and `runner.memory_mb`.
- Docker runner rejects raw Docker CLI argument passthrough and extra host mounts or volumes.
- `runner.cpus` and `runner.memory_mb` are valid for Docker-backed runners when supported by the local Docker environment. `runner.cpus` must be a positive finite number, and `runner.memory_mb` must be a positive integer. If either configured limit is unsupported, config validation fails before write with `CONFIG_INVALID`.
- Harbor runner requires `runner.harbor_task_ref`.
- SkyDiscover runners require `runner.skydiscover_task_ref`.
- SkyDiscover Python runner may set `runner.program_path`, default `"."`.
- `reward.type` is `none`, `exit_code`, `file`, `stdout_regex`, `harbor`, or `skydiscover`.
- `reward.type = "none"` is valid only with `runner.type = "none"` and rejects reward extractor fields such as `reward.path` and `reward.pattern`.
- `reward.direction` is `maximize` or `minimize`.
- `reward.primary_metric` defaults to `reward`, except SkyDiscover defaults to `combined_score`.
- `reward.type = "exit_code"` requires `reward.direction = "maximize"`.
- `artifacts.globs = []` means no extra artifacts.
- `artifacts.per_file_limit_bytes`, `artifacts.per_run_limit_bytes`, `logs.stdout_limit_bytes`, and `logs.stderr_limit_bytes` must be positive integers.
- `logs.*_limit_bytes` default to `10485760`.
- `env` is a map of valid environment variable names to strings. `secret_env` input values are single-line strings at least 4 UTF-8 bytes, or config-import retain markers. Names must match `^[A-Za-z_][A-Za-z0-9_]*$`.

Baseline trigger rule:

- Runtime-affecting fields trigger baseline: `source.default_source_ref`, all `runner.*`, all `reward.*`, `artifacts.*`, `logs.*`, `env.*`, `secret_env.*`, and timeout fields.
- Policy and metadata fields do not trigger baseline by themselves: `project.goal`, `project.task`, `project.allow_public_exp_create`, `public_source_import.*`, `mutable.*`, `visibility.*`, `metrics.reference.*`, tags, and Git author metadata.

Config edit rule:

- `project config import`, `project config set`, `project env`, and `project secret` changes are based on `latest_attempted_config_version`.
- `project config set` accepts TOML literals for any non-secret field, including arrays and maps. Setting a map or array replaces that complete field; it does not deep-merge. `[secret_env]` changes must use `project secret` or config import retain markers.
- A config edit that is byte-identical by `config_hash` to the current latest attempted version is a no-op and does not create a new version.
- Reverting to older config content creates a new monotonic config version unless it is identical to the current latest attempted version.
- Invalid runtime config cannot be made valid by metadata-only changes.
- `project validate` validates the latest attempted config.
- `project config import --dry-run` and `project config set --dry-run` parse and canonicalize input, compute the effective diff, determine whether baseline would be required, and run runtime capability checks such as Docker availability and resource support. They do not write SQLite rows, do not mutate files, do not execute baseline runners, and do not create audit events.

Config read/export rule:

- `project config show` and `project config export` default to `--version latest-attempted`.
- `--version latest-attempted` selects `projects.latest_attempted_config_version`.
- `--version active-valid` selects `projects.active_valid_config_version` and fails with `PROJECT_INVALID` when no active valid config exists.
- `--version <n>` selects an explicit positive retained config version number.
- Exported TOML always uses secret retain markers for `[secret_env]`, regardless of selected version.

## 2. Project Lifecycle

Project statuses:

- `valid`: `active_valid_config_version` has a passed baseline validation for its default source and runner configuration.
- `invalid`: the latest attempted runtime-affecting config version failed baseline, errored, timed out, or was skipped.
- `archived`: project is retained but blocked for new experiments and run/submit.

Archive/unarchive:

- `project archive` requires root/admin.
- Project archive fails with `RESOURCE_BUSY` when active validation, source import, run, submit, worktree maintenance, or other project maintenance locks exist.
- Archive is a pure state change. It does not delete Git refs, worktrees, sources, experiments, runs, artifacts, logs, credentials, or annotations.
- Archive stores `pre_archive_status`.
- `project unarchive` restores `pre_archive_status`.
- If a project was archived while invalid, unarchive returns it to `invalid`.
- If a project was archived while valid, unarchive returns it to `valid`.
- `project remove` is root-only and follows the archive-first, `--cascade`, and audit rules in [spec_lifecycle.md](spec_lifecycle.md).

Validation:

- Project creation and runtime-affecting config changes run baseline by default.
- `--skip-baseline-test` writes a valid schema change, stores a skipped validation record, leaves `active_valid_config_version` unchanged, marks the project invalid, and exits `0`.
- Skipped baseline validation is never treated as proof that a project is runnable. New experiments remain blocked until `project validate` passes.
- Baseline validation creates a `running` validation record before runner execution and updates it to a final status after capture.
- Stale `running` validation records are marked `interrupted` during later project maintenance, config, validation, or status operations.
- Baseline failure marks the project invalid and stores logs, artifacts, reward if parsed, and failure reason.
- Existing experiments keep using the config version bound at creation, including `env` and `secret_env`.
- Existing open experiments may continue using their bound valid config version after the project becomes invalid.
- New experiments require a valid project.

## 3. Project Init

Commands:

```text
alab project init local --config <path> --source-path <path> ...
alab project init git --config <path> --source-git <url> [--git-ref <ref>] [--source-subdir <path>] ...
alab project init empty --config <path> --source-empty ...
alab project init harbor --config <path> --harbor-task <path|skydiscover:path> [--source-path <path>|--source-git <url>|--source-empty] ...
alab project init skydiscover --config <path> --skydiscover-task <path|skydiscover:path> [--source-path <path>|--source-git <url>|--source-empty] ...
```

Common rules:

- Requires root key.
- `auth init` must already have run.
- Project init always creates exactly one project admin key when initialization writes the project record.
- The raw admin key is displayed exactly once and only its verifier is stored.
- The admin key is still created and displayed when baseline validation later fails and the retained project becomes `invalid`.
- If baseline validation fails during project init, ALab retains the project, source, config version, validation record, logs, artifacts, and failure reason. The project status becomes `invalid`.

Input precedence:

1. Load required `--config`.
2. Apply mode-specific source/Harbor/SkyDiscover data.
3. Apply allowed CLI metadata overrides: project `--name`, `--task`, `--goal`, and source selectors.
4. Validate source-independent schema fields. At this stage, missing `source.default_source_ref` is allowed only when the init command supplies one effective default source origin.
5. Stage the project repository and import/create the effective default source, enforcing any init-time source import limits before project rows are written.
6. If an adapter-derived editable source and an explicit caller source are both present, compare canonical tree hashes. Identical content dedupes normally; different content fails with `SOURCE_INVALID` and a stable source conflict reason.
7. Inject the staged canonical source ref into `source.default_source_ref` when the input config omitted it. If the input config supplied a different ref, fail with `CONFIG_INVALID`.
8. Validate the full canonical config.
9. Write project, source, config, path registry, and initial admin credential verifier rows in one short SQLite transaction after filesystem staging succeeds.
10. Render the raw admin key exactly once.
11. Run baseline unless skipped or not required by free evaluation.

Runtime config rules:

- A project must have a complete runner and reward policy before baseline validation, except free evaluation projects where `runner.type = "none"` and `reward.type = "none"` make baseline validation `not_required`.
- `--config` is required for every project init mode in V1.
- Runner, reward, artifact, log, env, secret, Docker, Harbor, and SkyDiscover runtime fields are read from project config, not from init flags.
- ALab must not silently default reward type. The config must provide a complete reward policy.
- Init source flags are the only init-time runtime-affecting overrides. They exist to bootstrap the initial default source during project creation, not to silently replace a conflicting `source.default_source_ref` already present in the input config.
- Project init accepts the same source limit options as source import (`--max-files`, `--max-total-bytes`, `--max-file-bytes`) for the staged initial source. Values must be non-negative integers. Malformed or negative limit values fail with `CONFIG_INVALID`; exceeded limits fail with `SOURCE_LIMIT_EXCEEDED` before source staging or project/source/config/admin credential rows are written.
- Remote Git source selection uses `--git-ref <branch|tag|sha>`.
- `--source-ref` always means an existing ALab source id or `alab/source/<source_id>` and must not be used for remote Git refs.
- `project init harbor` and `project init skydiscover` do not accept `--source-ref` in V1. A new adapter project must bootstrap its initial editable source from `--source-path`, `--source-git`, `--source-empty`, or an adapter-derived editable source. Existing ALab sources are project-scoped reproducibility records, not cross-project init inputs.
- Free evaluation projects support `project init local|git|empty`; adapter init modes `harbor|skydiscover` require their adapter runner refs and do not accept `runner.type = "none"`.

## 4. Source Model

External code enters ALab through immutable source refs:

```text
alab/source/<source_id>
```

Git storage:

- The CLI name maps to `refs/heads/alab/source/<source_id>` in the canonical repository.
- A source import creates one filtered snapshot commit in the canonical repository.
- Git imports do not preserve upstream history in V1.
- Snapshot fidelity follows Git semantics: file contents, paths, executable bit, and symlinks are preserved; mtime, owner, group, and extended attributes are not preserved.
- Source `tree_hash` uses `alab-tree-sha256-v1`: ALab builds a canonical manifest from the filtered tree sorted by repo-relative path. Each manifest entry records path bytes, Git file mode, entry kind, symlink target bytes for symlinks, and SHA-256 content hash for regular files. The final tree hash is `sha256:` plus the SHA-256 digest of the canonical manifest. It is independent of Git object hash format.
- Git submodules/gitlinks are not supported source entries in V1. If filtering leaves any gitlink entry, import fails with `SOURCE_INVALID` and a next action to vendor or expand the submodule contents before import.

Commands:

```text
alab source import --project <project_id> --source-path <path> [--source-subdir <path>] [--name <name>] [--max-files <n>] [--max-total-bytes <n>] [--max-file-bytes <n>]
alab source import --project <project_id> --source-git <url> [--git-ref <ref>] [--source-subdir <path>] [--name <name>] [--max-files <n>] [--max-total-bytes <n>] [--max-file-bytes <n>]
alab source import --project <project_id> --source-empty [--name <name>]
alab source list [--project <project_id>] [--include-archived]
alab source show <source_id> [--project <project_id>]
alab source archive <source_id> [--project <project_id>]
alab source unarchive <source_id> [--project <project_id>]
alab source remove <source_id> [--project <project_id>] (--dry-run|--force --confirm <source_id>) [--cascade] [--reason <text>]
```

Authorization:

- Standalone source commands require root/admin.
- Public `exp create --source-*` may inline import source into that project when public experiment creation and public source import policy allow it.

Source selection:

- A command that selects a source origin may use exactly one of `--source-ref`, `--source-path`, `--source-git`, or `--source-empty`.
- `--source-subdir` is allowed with local path and remote Git imports.
- Existing source references may be passed as either `src-<slug>-<suffix>` or `alab/source/src-<slug>-<suffix>`.
- CLI output renders the canonical `alab/source/<source_id>` form.
- Remote Git imports use `--git-ref <branch|tag|sha>` to select the upstream ref. If omitted, ALab resolves remote HEAD.
- `skydiscover:<path>` is a task/evaluator catalog URI, not an editable source kind in V1.

Source names:

- Source names are optional.
- If omitted, ALab derives a name from the origin:
  - local path basename for `--source-path`;
  - Git URL repository basename plus selected ref for `--source-git`;
  - `empty` for `--source-empty`;
  - Harbor task basename for Harbor-derived sources;
  - SkyDiscover benchmark basename for SkyDiscover initial program imports.
- Derived names must still be unique by normalized slug within the project.
- If a derived or supplied name conflicts, ALab appends a short deterministic suffix based on the source id for public inline import and fails with `NAME_CONFLICT` for root/admin standalone import unless `--name` is changed.

Default limits:

- `100000` files.
- `1073741824` total bytes.
- `104857600` bytes per file.

Limit rules:

- Root/admin imports may raise or lower limits.
- Public no-key inline imports use `[public_source_import]` limits.
- Public limits are project-configurable and have no separate hard-coded cap.
- Public callers may lower limits per command but may not raise them above the configured public limits. Policy-ceiling failures must be detected before source path reads, source copies, Git clones, source records, or experiment rows.
- If an import exceeds effective limits, the command fails with `SOURCE_LIMIT_EXCEEDED` and creates no source record or Git source ref.
- Public no-key remote Git imports may use existing non-interactive Git credential helpers on the local machine. They must render `PUBLIC_GIT_CREDENTIAL_HELPER_USED` when a helper is available or used, and Git prompts remain disabled.

Local path import:

- Captures current filesystem contents, not only Git HEAD.
- If the source path is inside a Git worktree, ALab uses Git-native ignore evaluation and imports tracked files plus untracked non-ignored files from the current filesystem state.
- In a Git worktree, tracked files are imported even when their names match built-in sensitive exclude patterns.
- Untracked files matching root `.alabignore` or built-in sensitive excludes are excluded even if Git would otherwise include them.
- In a Git worktree, `.alabignore` never excludes tracked files; tracked files remain part of the source snapshot and may only render warnings.
- Tracked sensitive files render `TRACKED_SENSITIVE_SOURCE_FILE`.
- If the source path is not inside a Git worktree, ALab applies root `.gitignore`, optional root `.alabignore`, and built-in sensitive excludes through `pathspec`.
- Always excludes `.git/` and `.alab/`.
- Does not auto-sync future origin changes.
- If filtering produces an empty tree, import succeeds and renders `SOURCE_EMPTY_AFTER_FILTER`. Explicit `--source-empty` does not warn.

Built-in sensitive excludes:

```text
.git/
.alab/
.env
.env.*
*.pem
*.key
id_rsa
id_ed25519
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.DS_Store
node_modules/
dist/
build/
coverage/
```

Remote Git import:

- Clones/fetches into a temporary directory.
- Resolves remote HEAD when `--git-ref` is omitted.
- Runs Git non-interactively and disables prompts.
- Existing Git credential helpers may be used for root/admin and public no-key imports, but a credential prompt that would block fails import.
- Records resolved commit.
- Supports subdir import.
- Does not keep a live upstream tracking relationship in V1.

Deduplication:

- ALab computes a normalized content tree hash after filtering and subdir selection.
- If an identical active source exists, ALab returns the existing source id/ref, appends a sanitized origin entry to `origin_metadata_json.origins`, and does not create a new source id or Git source ref.
- Archived sources are ignored for dedupe lookup. The same content may be re-imported as a new active source after the old source is archived.
- If the caller provided a different source name for deduplicated content, ALab renders `SOURCE_DEDUPED_NAME_IGNORED`.
- Source refs are immutable and never overwritten.

Source lifecycle:

- Active sources can create experiments.
- Archived sources remain usable for existing records and experiments that already reference them.
- Source archive is allowed only when the source is not the active default source.
- New experiment creation from archived source requires explicit `--source-ref` plus root/admin.
- `source unarchive` restores active status.
- `source remove` requires archived source and follows dependency and audit rules in [spec_lifecycle.md](spec_lifecycle.md).
- A source referenced by any project config version can never be hard-removed in V1 because config versions are immutable reproducibility and audit records.

## 5. Experiment Lifecycle

Experiment statuses:

- `open`: accepts run, submit, tags, and annotations.
- `closed`: final submission accepted; rejects run and submit; accepts observe, tags, annotations, and create-from-experiment.
- `archived`: retained but hidden from list/search/best by default; rejects run and submit; accepts show, create-from-experiment, and admin maintenance.

Create:

```text
alab exp create [--project <project_id>] --name <name> [--goal <goal>] [--path <dir>] [--tag <tag> ...] [--source-ref <ref>|--source-path <path>|--source-git <url>|--source-empty|--from-exp <exp_id>] [--git-ref <ref>] [--source-subdir <path>] [--from-commit final|latest|best|<sha>] [--mutable-include <pattern> ...] [--mutable-exclude <pattern> ...] [--visibility-scope none|same_project|explicit] [--visible-exp <exp_id> ...]
```

Rules:

- If project allows public experiment creation, no root/admin key is required in project context or with explicit `--project`.
- If project is private, root/admin is required.
- Project must be `valid`.
- Experiment names must be unique within a project by normalized slug. All callers, including public no-key callers, receive `NAME_CONFLICT` on conflict; ALab does not auto-suffix experiment names.
- Public no-key experiment creation may use a custom path when it passes realpath registration, empty-directory, and nesting checks.
- A custom experiment path is valid only when it does not exist or exists as a completely empty directory.
- If `--path` is omitted, ALab creates the worktree at `./<project_id>_<exp_id>` relative to the command cwd.
- The default worktree path must not already exist. If it exists, `exp create` fails and tells the caller to pass `--path`.
- The command cwd for a default worktree may be any directory that passes realpath registration and nesting checks. A registered project control context for the same project is allowed and creates the default experiment worktree as a child of that control context. A project control context for a different project is rejected. Experiment and inspection contexts may not contain nested project, experiment, or inspection contexts.
- The experiment origin comes from explicit source flags, `source.default_source_ref`, or `--from-exp`.
- A command may use at most one origin: one source flag or `--from-exp`.
- If no origin is provided, ALab uses `source.default_source_ref`.
- Inline source import follows the same ignore and limit rules as standalone source import.
- `--git-ref` is valid only with `--source-git`.
- `--from-exp` creates from an existing experiment commit instead of a source ref.
- `--from-commit` is valid only with `--from-exp`.
- If `--from-exp` is supplied and `--from-commit` is omitted, ALab uses `latest`.
- Source experiment must be visible to the caller or caller must be root/admin.
- Public projects allow no-key `--from-exp` from visible `open` or `closed` experiments. This is an explicit public inheritance capability, not public observe history.
- For public no-key callers, `visible` means public inheritance visibility as defined in [spec_observe_collaboration.md](spec_observe_collaboration.md): the intersection of the current project visibility policy evaluated from the public project context and the source experiment's stored visibility upper bound.
- Public inheritance visibility never uses a raw experiment token, but it still respects the source experiment's stored visibility upper bound so public `--from-exp` cannot expand access beyond the source experiment's creation-time narrowing.
- Archived source experiments require root/admin for `--from-exp`, even when their records would otherwise be visible by id.
- `--from-commit latest` resolves to the source experiment's latest run commit when present; if no run exists, it resolves to branch HEAD.
- `--from-commit final` requires a final commit.
- `--from-commit best` resolves to the best passed run and requires a qualifying parsed numeric reward.
- `--from-commit <sha>` accepts a full or unambiguous commit SHA only when it is reachable from the source experiment branch.
- The new experiment baseline commit for full-diff mutable enforcement is the source commit or resolved experiment commit.
- For `--from-exp`, the new experiment stores the source experiment's `source_id` as source lineage, stores the resolved experiment commit as `baseline_commit`, and records the `from_exp` selector in `experiments.metadata_json`. It does not create a new source row or source ref.
- Mutable override may narrow but not expand project mutable policy. ALab stores the experiment override and evaluates the effective mutable policy as the intersection of the project policy bound at experiment creation and the experiment override. The intersection is applied at every run and submit scope check.
- Visibility override may narrow but not expand project visibility policy. At experiment creation, ALab normalizes and stores the intersection of the current project visibility policy and the requested visibility override as the experiment visibility upper bound.
- Tags supplied at creation are normalized lowercase ASCII slugs, max 64 bytes.
- ALab stores `bound_config_version` and `bound_validation_id` from the active valid project state at creation.
- ALab creates branch `alab/exp/<exp_id>`, creates the worktree, writes context and token, writes worktree-local Git exclude rules for `.alab/`, and stores experiment metadata.

Archive/unarchive:

- `exp archive` requires root/admin.
- Archive fails with `RESOURCE_BUSY` when the experiment has an active run or submit lock.
- Archive never deletes branches, commits, run records, artifacts, annotations, tags, source refs, or final submission metadata.
- Archive stores pre-archive status.
- `exp unarchive` restores the pre-archive status.
- `exp remove` requires archived experiment and follows cascade and audit rules in [spec_lifecycle.md](spec_lifecycle.md).

Inspection checkout:

```text
alab exp checkout <exp_id> [--project <project_id>] --path <dir> [--commit final|latest|best|<sha>]
```

- Creates an inspection worktree with an inspection marker and inspection token.
- Inspection checkout is CLI-read-only, not filesystem-read-only.
- Uses detached HEAD at the resolved inspection commit.
- If modified after checkout, `status`, `observe`, and artifact export still operate on the pinned inspection commit and stored records.
- Continuing work from a checkout requires `alab exp create --from-exp <exp_id>`.

## 6. Worktree Maintenance

Commands:

```text
alab exp worktree remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--reason <text>]
alab exp worktree restore <exp_id> [--project <project_id>] --path <dir>
```

Rules:

- Both commands require root/admin.
- `remove` may run while the experiment is open, closed, or archived.
- `remove --dry-run` reports the registered path, dirty state when available, token revocation target, and planned trash move without deleting files, changing DB state, or writing audit rows.
- `remove` unregisters the worktree path, marks the path registry row `removed`, revokes the active worktree token, and sets `worktree_state = 'removed'`.
- `--force --confirm <exp_id>` is required; `--force` is an explicit discard of uncommitted local files.
- `remove` does not delete branches, run records, artifacts, logs, annotations, or submissions.
- `restore` requires `--path`.
- Restore path must not exist or must be empty and must not nest inside another registered context.
- `restore` checks out experiment branch HEAD, writes `.alab/context.json`, revokes any previous active worktree token, creates a new worktree token, writes the raw token to `.alab/token`, and writes worktree-local Git exclude rules for `.alab/`.
- `restore` sets `worktree_state = 'active'`.
- Restore never prints the raw token.

## 7. Mutable Scope

Mutable matching:

- Patterns are repo-relative.
- Path separators normalize to `/`.
- Pattern syntax is pathspec GitWildMatchPattern, matching Git-ignore-style semantics.
- Includes define candidate writable paths.
- Excludes remove paths.
- Excludes win.
- `.alab/**` is always excluded.
- Rules apply to added, modified, deleted, renamed, copied, and type-changed paths.
- Added and modified paths are checked by their new path. Deleted paths are checked by their old path. Renames and copies require both the source path and destination path to be allowed by the effective mutable policy.
- Matching is based on repo-relative Git paths.
- Symlink entries are governed by the symlink path stored in Git, not by resolving the target.
- V1 allows Git symlinks in sources and experiment commits. This is Git fidelity, not an OS sandbox guarantee.

Experiment mutable override:

- May remove include coverage.
- May add excludes.
- May not add writable paths outside project policy.
- If no experiment override is provided, project policy is used.
- Effective mutable policy is computed as a deterministic intersection: a path is writable only when it is allowed by the project policy and by the experiment override. Excludes from either side win. This avoids requiring static proof that two GitWildMatch pattern sets have a subset relationship.

## 8. Run Lifecycle

Command:

```text
alab run --message <message>
```

Rules:

- Must run inside experiment context.
- Requires valid worktree token.
- Project must not be archived.
- Experiment must be `open`.
- Experiment `worktree_state` must be `active`.
- Uses the experiment's bound valid config version.
- `--message` is required and max 300 bytes after UTF-8 encoding.
- If another run or submit is active for the same experiment, fail fast with `EXPERIMENT_BUSY`.

Git state rules:

- HEAD must be attached to registered `alab/exp/<exp_id>` branch.
- Detached HEAD, different branch, merge, rebase, cherry-pick, bisect, or unresolved conflict state fails before staging.
- ALab inspects staged, unstaged, deleted, renamed, copied, and untracked non-ignored changes.
- Every changed path must be allowed by effective mutable policy.
- ALab stages all allowed changed paths.
- If staged content exists, ALab creates one commit with `ALab run: <message>`.
- The automatic commit includes all mutable-allowed staged, unstaged, deleted, renamed, copied, and untracked non-ignored changes. ALab does not preserve a caller's pre-existing staged set as a separate concept.
- Manual commits are allowed when HEAD is on the registered branch and the full diff from the experiment baseline commit to HEAD is allowed by effective mutable policy.
- If HEAD already contains valid manual commits and the worktree also has dirty changes, ALab first validates the full diff from the experiment baseline commit to the current HEAD, then stages and auto-commits the dirty changes, and finally repeats the full-diff mutable check against the new target commit.
- Existing staged changes are included in the same mutable-scope inspection and automatic commit as unstaged and untracked changes.
- If no changes exist, no commit is created and the run points at current HEAD.

Run execution flow:

1. Resolve experiment and token.
2. Validate project and experiment state.
3. Acquire experiment run/submit lock.
4. Check branch and Git operation state.
5. Check mutable scope for dirty changes.
6. Allocate `run_id` and create a `running` run record.
7. Stage and commit if needed, using the allocated run id in commit trailers.
8. Check full-diff mutable scope.
9. If full-diff scope fails after an ALab auto commit, roll back only that auto commit with mixed-reset semantics, preserving file changes as unstaged worktree changes, store the rolled-back commit hash and explanation on the run record, mark the run `error`, render `SCOPE_VIOLATION` details and next action, and release the lock.
10. If full-diff scope fails because of an existing manual commit or any state ALab cannot safely roll back, leave HEAD and the worktree unchanged, store violation paths and explanation on the run record, mark the run `error`, render `SCOPE_VIOLATION` details and next action, and release the lock.
11. Create clean temporary `workspace` checkout at target commit.
12. Ensure the temporary `workspace` does not contain `.alab/context.json` or `.alab/token`; runners must not receive the submit-capable worktree token through the checkout.
13. Create empty temporary `run_dir`.
14. Execute runner using the experiment's bound config version with stdin closed.
15. Attempt reward extraction, including for non-zero runner exit.
16. Capture logs and artifacts.
17. Update run record from `running` to final status.
18. Update experiment latest run and latest commit.
19. Release experiment lock.

Commit trailer rules:

- If ALab creates a commit, it allocates the run id before commit creation.
- Automatic commit subject is `ALab run: <message>`.
- Automatic commit body includes `ALab-Run: <run_id>`, `ALab-Experiment: <exp_id>`, and `ALab-Config-Version: <version>`.
- ALab sets both Git author and committer from the experiment's bound `[git]` config.

Run record rules:

- A `running` run record is written before any auto commit.
- Failed, errored, and timed-out runs do not roll back commits created before runner execution.
- Same commit can have multiple run records.
- Ranking uses parsed numeric rewards, not uniqueness by commit.
- Stale `running` records are marked `interrupted` before later run/submit/archive operations.
- Run archive, unarchive, and remove behavior is defined in [spec_lifecycle.md](spec_lifecycle.md).

## 9. Submit Lifecycle

Command:

```text
alab submit --message <message> --summary <text>|--summary-file <path> --feedback <text>|--feedback-file <path> --ref <exp_id|none> [--ref <exp_id> ...] [--rerun]
```

Rules:

- Must run inside experiment context with valid worktree token.
- Project must not be archived.
- Experiment must be `open`.
- Experiment `worktree_state` must be `active`.
- `--message`, summary, feedback, and at least one `--ref` are required.
- Summary accepts exactly one of direct text or `--summary-file`.
- Feedback accepts exactly one of direct text or `--feedback-file`.
- Summary and feedback files resolve relative to the current command cwd.
- V1 does not support `--summary-stdin` or `--feedback-stdin`.
- `--ref none` is mutually exclusive with experiment refs.
- Experiment refs are deduplicated preserving first-seen order.
- Every experiment id passed through `--ref <exp_id>` must be visible to the submitting token or caller.
- Invisible refs fail without disclosing additional record details.
- Submit message, summary, and feedback inputs are limited to 300, 65536, and 65536 bytes respectively after UTF-8 encoding.
- Summary and feedback must not contain exact active `secret_env` values for the experiment's bound config version. If an exact secret value is found, submit fails without storing final submission text.
- In free evaluation mode, `--rerun` fails with `CONFIG_INVALID`; free submissions do not execute the run flow and do not create run, log, artifact, or reward rows.
- In free evaluation mode, dirty worktrees are committed directly with subject `ALab submit: <message>` and metadata including submission id, experiment id, config version, and `ALab-Evaluation: none`; mutable scope checks still apply, and a violating automatic commit is rolled back before failure.
- In standard evaluation mode, if `--rerun` is present, always execute the run flow.
- In standard evaluation mode, if worktree changes exist, execute the run flow.
- When submit executes the run flow, it reuses `submit --message` as the run message. Any automatic commit created by that run still uses the normal `ALab run: <message>` subject, and the submission row separately stores the same submit message.
- If no worktree changes exist, reuse the most recent run for current HEAD and the experiment's bound config version only when that run is `passed`.
- If no worktree changes exist and no reusable passed run exists, submit fails with exit code `1` and a next action to use `--rerun`.
- If final run status is `passed`, store one `experiment_submissions` row with message, summary, feedback, refs, final commit, and final run id, then close the experiment.
- In free evaluation mode, store one `experiment_submissions` row with `final_run_id = NULL`, final commit, message, summary, feedback, and refs, then close the experiment.
- If final run status is not `passed`, keep experiment open and do not store final summary, feedback, refs, final commit, or final run id. The run record remains stored.
