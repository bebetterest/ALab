# ALab Implementation Progress Log

This file is the historical implementation journal for ALab V1. Read `docs/progress.md` first for the current dashboard, then `docs/progress_pipeline.md` for the active queue. Use `docs/progress_closed_gaps.md` only when planned work might duplicate a closed proof family. Older `Known incomplete areas` entries below are historical only unless they are promoted into `docs/progress_pipeline.md`.

## Maintenance Rules

- Append detailed batch entries here after updating `docs/progress_pipeline.md`, and `docs/progress.md` when gate-level status changes.
- Keep entries concise: implemented behavior, verification, and residual risk.
- Do not use this log as the current backlog; `docs/progress_pipeline.md` is the current source of truth for next work.
- When this English file changes, update `docs/progress_log_cn.md` in the same change.

## Detailed Implementation Log

## 2026-05-17 First Runnable Milestone

Implemented:

- Python package scaffold with `pyproject.toml`, `src/alab/`, tests, and `alab` entry point.
- Strict text renderer, stable error rendering, global option pre-scan, command registry, context-aware help, and command preflight.
- ALAB home layout, SQLite WAL schema, root/admin/token HMAC verifier storage, context marker detection, path registry, and audit event foundation.
- Local project initialization from local/Git/empty sources, source snapshot refs, baseline validation, local runner execution, log/artifact storage foundations, experiment worktree creation, run, submit, basic status/list/observe runs, and audit list.
- Smoke tests covering auth init/config show and the local project -> experiment -> run -> submit workflow.

Known incomplete areas:

- Full lifecycle maintenance for every object.
- Full observe filters/search/best ranking, annotations, inspection checkouts, and project config mutation.
- Source import mutation after project init, cache/catalog/backup workflows, and Docker/Harbor/SkyDiscover adapters.
- Full CLI golden matrix required by `docs/spec_tests.md`.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- Manual smoke with temporary `ALAB_HOME`: `auth init`, `project init local`, `exp create`, `run`, and `submit`.

## 2026-05-17 Local Workflow Expansion

Implemented:

- Project config show/export/import/set, metadata-only inherited config versions, runtime-affecting baseline validation, and manual `project validate`.
- Project env set/unset/list and project secret set/unset/list. Raw secret values remain local plaintext in storage but are not rendered or exported; exports use retain markers.
- Post-init source import/show/list/archive/unarchive/remove dry-run for local/Git/empty source snapshots, including active-source tree dedupe.
- Observe run show/archive/unarchive/remove, artifact list/show/export/archive/unarchive/remove, and log list/show/export/archive/unarchive/remove for local visible records.
- Project and experiment archive/unarchive plus dry-run guarded remove commands.
- Experiment tag add/remove/list for admin/root keys and owning experiment worktree tokens.
- Audit show and audit list filters.
- Expanded smoke tests for config export/set, post-init source import, token-scoped tags, log export, and artifact export.

Known incomplete areas:

- Lifecycle remove still needs full V1 trash staging, complete blocker coverage, and deeper cascade accounting.
- Observe visibility is conservative: root/admin project scope and owning experiment token scope are implemented, but full same-project/explicit visibility search and best ranking remain pending.
- Annotations, inspection checkouts, worktree restore, experiment token maintenance, project validation lifecycle maintenance, cache/catalog/backup workflows, and Docker/Harbor/SkyDiscover adapters remain pending.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-17 Collaboration Context Expansion

Implemented:

- Experiment worktree remove/restore with path registry updates, active worktree token revocation, new worktree token creation, marker rewrites, and audit events.
- Experiment token list/revoke/regenerate for worktree and inspection token modes. Regeneration writes the new raw token to the registered path and never renders it.
- Inspection checkout creation and removal. Inspection contexts get detached Git worktrees, inspection markers, scoped inspection tokens, and read-only CLI observe access.
- Annotation add/edit/archive/unarchive/remove plus observe annotations list/show. The current implementation supports experiment/run/artifact targets and common experiment-context path/line shorthand, revision history, project/private visibility, and secret-value body rejection.
- Smoke coverage for token listing/regeneration, inspection checkout observe/remove, annotation add/edit/show/archive/remove dry-run, and worktree remove/restore.

Known incomplete areas:

- Annotation branch-name commit resolution and file/line Git validation are covered by later progress entries.
- Observe visibility and search/best ranking are covered by later progress entries.
- Worktree and checkout trash staging semantics are covered by later progress entries.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`

## 2026-05-17 Observe Experiment Expansion

Implemented:

- `exp search`, `exp show`, `exp best`, and matching `observe experiments search/show/best` aliases now use the same structured experiment result block as `exp list`.
- Experiment list/search/best support pagination, status/tag/source/name/time/config-version filters, reward min/max filtering, basic sort fields, and case-insensitive search across experiment metadata, tags, project task text, final submission text, and latest annotation bodies.
- Best ranking picks at most one parsed passed run per visible experiment, respects reward direction, excludes archived runs by default, and uses reward-policy identity comparison for the default active-valid policy case.
- Token observe visibility now computes the intersection of the current project visibility policy and the source experiment's stored visibility upper bound. Tokens can always see their own experiment and can see same-project or explicit peer experiments only when both policies allow it.
- Runs, artifacts, logs, annotations, checkout target resolution, and annotation target resolution now share the same visible-experiment calculation instead of hard-coding own-experiment-only observe access.
- Smoke coverage now exercises same-project token visibility, experiment search, experiment show, and reward-ranked best selection across two experiment worktrees.

Known incomplete areas:

- Best warning details are implemented in the later Best Incomparable Warning section.
- Observe filters for runs/artifacts/logs/annotations still need the complete documented matrix.
- Public from-experiment inheritance is tracked in the later Public From-Experiment Inheritance section.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-17 Context Repair Expansion

Implemented:

- `context show` now renders marker and path-registry status for the current or requested path, including registered state and present/moved/conflict/unregistered path status.
- `context repair --path <dir>` now repairs path registry entries for project, experiment, and inspection markers. It supports root/admin credentials and matching self-token repair when the previous registered path no longer exists.
- Repair updates registry path/hash data, rewrites marker metadata with `repaired_at`, and records an audit event using existing object types.
- Smoke coverage verifies context show and admin repair inside an experiment worktree.

Known incomplete areas:

- Self-token repair Git checks are implemented in the later Context Self-Repair Git Checks section.
- Repair currently updates registry state directly; full V1 lifecycle/trash semantics remain a separate pending area.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-17 Credential And Validation Lifecycle Expansion

Implemented:

- `key create`, `key list`, and `key revoke` now manage root/admin credential rows without storing raw key material. `key create` prints the generated raw admin key exactly once.
- `project validation archive`, `project validation unarchive`, and `project validation remove` now support admin/root lifecycle maintenance for non-active project validation rows.
- Validation remove supports dry-run, confirmation, cascade deletion of validation logs/artifacts, blockers for active/running/not-archived validations, and lifecycle audit events.
- TOML export now drops optional `None` fields before calling `tomli-w`, matching the official dependency behavior instead of relying on fallback serialization.
- Smoke coverage now exercises key creation/list/revoke and validation archive/unarchive/remove.

Known incomplete areas:

- Validation remove reference-counting and trash staging are implemented in the later Validation Remove Reference-Counted Trash section.
- Broader local maintenance commands and SkyDiscover catalog lifecycle commands are tracked in later progress sections.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Docker Runner Expansion

Implemented:

- Added a unified `run_configured_runner` boundary. Local validation/run workflows still use the local subprocess path, while Docker configs now execute through the same runner result model.
- Docker runner now supports explicit `runner.image` and `runner.dockerfile` plus `runner.context` configs, `runner.command` or `runner.shell`, workspace mount at `/app`, run directory mount at `/logs/alab`, container-visible ALab env values, and `runner.network = "default"|"none"`.
- Missing configured images trigger `docker pull`; Dockerfile configs compute an ALab-owned cache key from Dockerfile content, `.dockerignore`, effective build context bytes, build args, target, and platform, then tag images as `alab-cache:<digest>`.
- Dockerfile cache metadata is recorded in `cache_entries` so existing `cache prune --docker-images|--all` can see ALab-owned image cache rows.
- Added Docker runner unit/contract coverage without requiring a live Docker daemon: `.dockerignore` cache-key behavior, workspace escape rejection, fake-Docker run contract, and structured not-implemented adapter errors.

Known incomplete areas:

- Docker capability probes, image cache pruning, and pre-write resource checks are tracked in the later Docker Capability And Cache-Prune Expansion section.
- Deeper per-architecture Docker platform specificity remains pending.
- Harbor and SkyDiscover adapters remain registered or modeled by config schema but are not implemented runners yet.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`

## 2026-05-17 Local Maintenance Expansion

Implemented:

- `project secret gc --apply` deletes unreferenced raw secret values and writes a lifecycle audit event. Without `--apply`, it reports the current unreferenced set without deleting.
- `project locks clear-stale` deletes expired project locks and reports cleared lock names.
- `backup prune --keep <n>|--older-than <days>` prunes local migration backup files under `ALAB_HOME/backups`.
- `cache prune` validates V1 selector combinations and marks matching rebuildable cache rows removed, with safe path deletion for ALab-owned cached paths.
- Smoke coverage now verifies zero-count secret GC and stale lock clearing, plus backup prune and cache prune through root credentials.

Known incomplete areas:

- Docker image cache removal is tracked in the later Docker Capability And Cache-Prune Expansion section; SkyDiscover environment cleanup is tracked in the later SkyDiscover Python Runner Expansion section.
- Backup prune deletes matching files directly; full migration backup creation/checksum coverage remains pending.
- SkyDiscover catalog add/update/show/remove is tracked in the later SkyDiscover Catalog Expansion section.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`

## 2026-05-17 SkyDiscover Catalog Expansion

Implemented:

- Replaced the remaining catalog stubs with root-gated `catalog skydiscover add/update/show/remove` handlers.
- `add` clones a selected origin into `ALAB_HOME/sources/skydiscover`, resolves `--ref`, `--commit`, or upstream `main` to an exact pinned commit, checks out that commit, stores catalog metadata, and audits the lifecycle event.
- `update` verifies the local catalog is a clean Git repository, refreshes from the selected origin, pins an exact commit, updates metadata, and audits the update.
- `show` reads only local SQLite state and renders the active catalog without fetching from the network.
- `remove` requires `--force --confirm skydiscover`, blocks active project config/open experiment references to `skydiscover:` strings, removes the local catalog path under `ALAB_HOME/sources`, marks metadata removed, and audits the removal.
- Config validation now resolves `skydiscover:<path>` refs for Harbor-compatible task refs and SkyDiscover Docker/Python evaluator refs against the active pinned catalog without auto-fetching.
- Smoke coverage uses local Git upstreams, so catalog add/update/show/remove and catalog-ref validation are tested without network access.

Known incomplete areas:

- Catalog URI resolution is wired into project init and project config import/set. Python evaluator materialization and runner execution are tracked in the later SkyDiscover Python Runner Expansion section; Docker evaluator execution is tracked in the later SkyDiscover Docker Runner Expansion section.
- SkyDiscover initial editable-source bootstrap from benchmark metadata is tracked in the later Adapter-Derived Source Bootstrap section.
- `update --origin-url` supports changing the origin after verifying the current local repository, but deeper upstream trust and dirty-state diagnostics remain minimal.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Docker Capability And Cache-Prune Expansion

Implemented:

- `config validate --refresh-capabilities` now probes Docker availability, Linux container platform reporting, and `docker run` CPU/memory flag support, then stores safe diagnostic rows in `runtime_capabilities`.
- Docker capability rows are cached by runtime fingerprint and reused when the fingerprint is unchanged; refresh clears the cached Docker rows before probing.
- `runtime_capabilities.status` now has the documented `supported|unsupported|error` check for new homes.
- Project init and project config import/set now consult the cached Docker probes and reject unsupported configured `runner.platform`, `runner.cpus`, or `runner.memory_mb` before writing a project config version. Docker availability errors still flow into saved baseline/run records instead of blocking config persistence.
- `cache prune --docker-images` now removes ALab-owned Docker image tags with `docker image rm` before marking cache rows removed. If Docker cleanup fails, the row remains active and the command emits a `DOCKER_CACHE_PRUNE_FAILED` warning block.
- Docker runner tests now cover capability refresh persistence, pre-write resource-limit rejection, and ALab-owned image removal through fake Docker CLIs, still without requiring a live Docker daemon.

Known incomplete areas:

- Docker platform enforcement is intentionally coarse in this slice: a reported non-Linux container runtime blocks configured `runner.platform`, but per-architecture/platform matrix probing is still pending.
- Harbor runner execution is tracked in the later Harbor Runner Expansion section.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 SkyDiscover Python Runner Expansion

Implemented:

- `run_configured_runner` now supports `runner.type = "skydiscover_python"` through the same structured runner result model used by local and Docker runners.
- SkyDiscover Python evaluator refs are resolved against the active pinned catalog at validation/run time, then copied into a hidden staging bundle outside the editable workspace and run directory.
- Evaluator code executes in a subprocess through an ALab wrapper. The main ALab process does not import evaluator code, and visible stdout is a safe summary containing task ref, pinned commit, evaluator mode, metric names, reward, and the explicit `not-os-sandbox` notice.
- Raw evaluator stdout/stderr and wrapper failure tracebacks are stored as hidden log streams, with configured secret bytes redacted before storage.
- Returned evaluator data is split into structured metrics and adapter feedback. SkyDiscover reward parsing uses the configured primary metric, and falls back to averaging finite numeric top-level metrics when the default `combined_score` is absent.
- Python dependency manifests create or reuse ALab-managed `uv` environments under `ALAB_HOME/cache/skydiscover-python-envs`. Cache rows now store the environment path, and `cache prune --skydiscover-envs|--all` safely removes those paths.
- Added direct runner coverage for hidden bundle materialization, hidden stdout capture, metric/reward parsing, and fake-`uv` environment cache reuse. Added a smoke test for catalog-backed baseline validation with stored metrics and hidden logs.

Known incomplete areas:

- SkyDiscover Docker evaluator execution is tracked in the later SkyDiscover Docker Runner Expansion section.
- SkyDiscover initial editable-source bootstrap from benchmark metadata is tracked in the later Adapter-Derived Source Bootstrap section.
- The Python evaluator is intentionally not an OS sandbox; this implementation exposes that in visible summaries but does not add process isolation beyond subprocess execution.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 SkyDiscover Docker Runner Expansion

Implemented:

- `run_configured_runner` now supports `runner.type = "skydiscover_docker"` through the same structured runner result model used by local, Docker, and SkyDiscover Python runners.
- SkyDiscover Docker evaluator refs are resolved against the active pinned catalog at validation/run time, then copied into a hidden staging bundle outside the editable workspace and run directory.
- Evaluator Dockerfiles build into ALab-owned `alab-cache:<digest>` image tags with cache rows. The cache key includes hidden bundle build inputs plus whitelisted build settings.
- Evaluator runs mount the candidate workspace at `/workspace`, run output at `/logs/alab`, and the hidden evaluator bundle read-only at `/alab/evaluator`, then execute `/alab/evaluator/evaluate.sh` through `/bin/sh`.
- Raw evaluator stdout/stderr and Docker build/setup output are stored as hidden log streams, with configured secret bytes redacted before storage.
- Evaluator stdout is parsed as JSON, split into structured metrics and adapter feedback, and `artifacts` JSON is kept in feedback rather than file artifact rows unless regular artifact globs capture files.
- Added direct fake-Docker runner coverage and a catalog-backed smoke baseline test covering hidden bundle staging, hidden mount separation, metric/reward parsing, feedback artifacts JSON, hidden logs, and Docker image cache rows.

Known incomplete areas:

- Harbor runner execution is tracked in the later Harbor Runner Expansion section.
- SkyDiscover initial editable-source bootstrap from benchmark metadata is tracked in the later Adapter-Derived Source Bootstrap section.
- Docker platform enforcement remains coarse and still needs deeper per-architecture/platform probing.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Harbor Runner Expansion

Implemented:

- `run_configured_runner` now supports `runner.type = "harbor"` through the same structured runner result model used by local, Docker, and SkyDiscover runners.
- Harbor task refs can point to local task directories or `skydiscover:<path>` catalog refs that resolve to Harbor-compatible tasks.
- Harbor task validation covers the strict V1 subset: `task.toml`, `tests/test.sh`, shared environment image or `environment/Dockerfile`, separate verifier image or `tests/Dockerfile`, Linux-only execution, and strict failures for multi-step, Windows/non-Linux, GPU, storage, MCP, healthcheck, services, Compose, raw Docker passthrough, host mounts, and placeholder values.
- Harbor literal task environment values are injected as secret environment values for verifier execution and participate in exact-byte log redaction.
- Harbor verifiers materialize into hidden bundles outside editable workspaces and run directories. Docker runs mount candidate workspace at `/workspace`, run output at `/logs/alab`, and the hidden Harbor bundle read-only at `/alab/harbor`.
- Harbor reward parsing reads `run:/logs/verifier/reward.json` or `run:/logs/verifier/reward.txt`; JSON rewards populate structured metrics and use `reward.primary_metric`, defaulting to `reward`.
- Verifier Dockerfiles build into ALab-owned `alab-cache:<digest>` image tags with cache rows. Task `environment.allow_internet=false`, `environment.cpus`, and `environment.memory_mb` map to Docker run settings unless overridden by config.
- Added direct fake-Docker Harbor runner coverage for shared verifier execution, hidden log redaction, network/resource mapping, hidden bundle mounts, and unsupported-field rejection. Added a smoke baseline test covering project init with a local Harbor task ref.

Known incomplete areas:

- Harbor adapter-derived editable-source bootstrap from task `source` metadata is tracked in the later Adapter-Derived Source Bootstrap section.
- Harbor task text precedence from `instruction.md` into project task metadata is implemented in the later Adapter-Derived Source Bootstrap section.
- Deeper Docker platform specificity remains pending.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Adapter-Derived Source Bootstrap

Implemented:

- `project init harbor` now derives the editable default source from supported Harbor task `source` metadata. The source path must be task-relative, stay inside the task directory, exist, and avoid verifier/private top-level paths such as `tests/`, `environment/`, and `solution/`.
- Harbor tasks without a supported editable source fall back to an empty source when the caller did not provide an explicit source selector. This matches the V1 Harbor fallback rule and still requires baseline validation unless skipped.
- Harbor `instruction.md` now becomes visible project task text only when the ALab config task is empty and the caller did not provide `--task`; explicit config or CLI task text still wins.
- `project init skydiscover` now derives the editable default source from SkyDiscover benchmark metadata (`benchmark.toml`, `metadata.toml`, `skydiscover.toml`, or JSON equivalents) or conservative conventional starter names such as `initial_program`, `starter`, or `program.py`.
- SkyDiscover imports only the initial program file or directory, never the whole benchmark directory, evaluator files, private data, or dependency manifests. When no initial program is found and no explicit source selector is supplied, init fails with `SOURCE_INVALID` and asks for an explicit source.
- Adapter init now compares canonical ALab tree hashes when an explicit caller source and adapter-derived source are both present. Identical trees dedupe; mismatches fail before project rows are written.
- Source origin metadata records safe adapter summaries and relative source paths without storing hidden asset bytes or evaluator/verifier contents.
- Added smoke coverage for Harbor declared-source import, adapter explicit-source conflict rejection, SkyDiscover metadata initial-program import, and SkyDiscover missing-initial failure.

Known incomplete areas:

- Docker platform specificity is covered by the later Docker platform native fallback milestone.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -k "harbor_project_init_uses_declared_source or adapter_init_rejects_conflicting_explicit_source or skydiscover_project_init_uses_initial_program_metadata or skydiscover_project_init_requires_initial_program_without_explicit_source"`
- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Public From-Experiment Inheritance

Implemented:

- `alab exp create --from-exp <exp_id>` now creates a new experiment worktree from an existing experiment commit instead of creating a new source row.
- Public no-key inheritance is capped by the intersection of current project visibility policy and the source experiment's stored visibility upper bound. Public callers can inherit only visible open/closed experiments; archived source experiments require root/admin.
- Token-context callers can inherit only token-visible open/closed experiments. Root/admin callers can inherit archived experiments as well.
- `--from-commit latest` resolves to the source experiment latest run commit when present and otherwise to the source experiment branch HEAD. `final`, `best`, and explicit reachable commit selectors are supported with stable failures for missing final/best commits or unreachable commit ids.
- New experiments store source lineage via the source experiment's `source_id`, record the resolved inherited commit as `baseline_commit`, and persist a `creation_origin.kind = "from_exp"` selector in experiment metadata.
- Added smoke coverage for public inheritance from the latest commit and public visibility-upper-bound rejection.

Known incomplete areas:

- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -k "public_exp_create_from_exp_uses_latest_commit or public_from_exp_respects_visibility_upper_bound"`
- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Public Inline Source Import

Implemented:

- `alab exp create --source-path|--source-git|--source-empty` now performs an inline source snapshot import before creating the experiment worktree.
- Inline imports share the same snapshot commit, canonical tree hash, active-tree dedupe, source metadata, Git submodule rejection, and audit path as standalone `alab source import`.
- Public no-key callers are limited by `[public_source_import]`; they can lower limits per command but cannot exceed the project policy. Root/admin inline imports use the normal source import defaults and may override them like standalone import.
- New experiments created from inline imports record `creation_origin.kind = "inline_source"` in metadata and bind to the imported or deduped source id.
- Added smoke coverage for public inline source creation and public policy limit rejection with no leaked source row.

Known incomplete areas:

- Remote public Git import still needs the documented credential-helper warning surface.
- Local source fidelity is still simplified compared with the full Git-aware `.alabignore`/tracked-file rules.
- Deeper Docker platform specificity remains pending.

Verification:

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Local Source Fidelity

Implemented:

- Local path source import now detects when the selected path is inside a Git worktree and imports tracked files plus untracked Git-nonignored files from the current filesystem state.
- Tracked files are imported even when they match built-in sensitive excludes or root `.alabignore`; the source result renders `TRACKED_SENSITIVE_SOURCE_FILE`.
- Untracked files matching Git ignore rules, root `.alabignore`, or built-in sensitive excludes are filtered out.
- Non-Git directory imports now apply root `.gitignore`, root `.alabignore`, and built-in sensitive excludes before snapshotting.
- Filtering to an empty tree now succeeds and renders `SOURCE_EMPTY_AFTER_FILTER`; explicit `--source-empty` remains warning-free.
- Added smoke coverage for Git tracked sensitive files, untracked `.gitignore`/`.alabignore` filtering, and empty-after-filter source import.

Known incomplete areas:

- The fallback ignore matcher used when `pathspec` is not installed is intentionally simpler than the dependency-backed GitWildMatch implementation.
- Remote public Git import still needs the documented credential-helper warning surface.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -k "source_import_respects_git_and_alab_ignore_rules or source_import_empty_after_filter_warns" -q`
- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Worktree And Checkout Trash Staging

Implemented:

- `exp worktree remove` now stages the registered worktree path into ALab trash before mutating SQLite rows or writing the lifecycle audit event.
- `exp checkout remove` now uses the same trash staging path for inspection checkout directories.
- Actual remove records sanitized trash metadata, token revocation targets, dirty state for submit-capable worktrees, and whether the registered filesystem path was already absent.
- If the SQLite transaction fails after a filesystem move, ALab best-effort restores the staged path to its original location and reports `STORAGE_ERROR` if restore fails.
- After DB/audit success, ALab deletes the staged trash immediately. If immediate deletion fails, it records an active `cache_entries.cache_kind = 'trash'` row for later `cache prune --trash --older-than <days>` or `cache prune --trash-all`.
- `cache prune --trash-all` and top-level `--all` can now remove active trash cache rows, including home trash paths and sanitized same-parent fallback labels.
- Added smoke coverage for trash cache pruning, worktree remove dry-run/actual trash metadata, token/path state updates, and inspection checkout missing-path reconciliation.

Known incomplete areas:

- Whole-project, whole-experiment, validation, run, artifact, log, and annotation lifecycle completion are covered in later progress entries.
- Standalone artifact/log remove is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-18 Experiment Remove Cascade Trash Staging

Implemented:

- `exp remove --cascade` now checks active experiment locks before actual deletion and reports a stable blocker in dry-run output.
- Whole-experiment remove now stages registered submit worktrees, inspection checkouts, unshared experiment log files, and unshared experiment artifact blobs into ALab trash before DB/audit mutation.
- If DB/audit mutation fails after staging, ALab best-effort restores every staged path in reverse order and returns `STORAGE_ERROR` if restore fails.
- Experiment token rows are revoked and retained for audit instead of being hard-deleted. Experiment path registry rows are marked `removed`, preserving reusable removed path semantics.
- Audit metadata records sanitized filesystem target count, absent count, trash mode/label, object kind, object id, and original path hashes without raw token or file contents.
- Experiment branch ref deletion is covered in a later progress entry.
- Immediate trash deletion reuses the same pending trash cache-row path as worktree/checkout remove when cleanup fails.
- Added smoke coverage for experiment remove cascade staging across worktree, inspection checkout, stdout/stderr log files, and artifact blobs.

Known incomplete areas:

- Annotation standalone remove revision-count audit is covered in a later progress entry; standalone artifact/log remove is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths`

## 2026-05-18 Project Remove Whole-Tree Trash Staging

Implemented:

- `project remove --cascade` now checks active project locks and reports a stable dry-run blocker before actual deletion.
- Whole-project remove now stages the project root, project control path, and active registered experiment/inspection paths into ALab trash before DB/audit mutation.
- Project remove deduplicates nested filesystem targets so paths already covered by the project root are not staged twice.
- If DB/audit mutation fails after staging, ALab best-effort restores every staged path in reverse order and returns `STORAGE_ERROR` if restore fails.
- Project admin credentials and experiment/inspection token rows are revoked and retained for audit. Project path registry rows are marked `removed` and retained for removed-path reuse.
- Audit metadata records sanitized filesystem target count, absent count, trash mode/label, target kind/object id, and original path hashes without raw filesystem paths, token values, or file contents.
- Added smoke coverage for project whole-tree cascade staging across project root, control path, experiment worktree, inspection checkout, retained credential/path rows, dependent DB record deletion, and pending trash cleanup.

Known incomplete areas:

- Annotation standalone remove revision-count audit is covered in a later progress entry; standalone artifact/log remove is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Observe List Sort Whitelists

Implemented:

- Added a shared `--sort <field>:<asc|desc>` parser for list-style observe rows with command-specific field whitelists and stable `CONFIG_INVALID` errors for unknown fields or bad directions.
- `runs list` now supports `started`, `ended`, `reward`, `status`, `config-version`, and `exit-code` sorting.
- `artifacts list` now supports `created`, `path`, `size`, `status`, and `content-hash` sorting.
- `logs list` now supports `created`, `stream`, `size`, `stored-bytes`, `hidden`, and `truncated` sorting.
- `annotations list` now supports `created`, `updated`, `target-type`, `target-id`, `status`, and `created-by` sorting.
- `exp best` now rejects user-provided `--sort` with `CONFIG_INVALID` because best ranking is fixed to reward-policy identity.
- Updated observe collaboration specs, README status, and local agent/core guides.

Known incomplete areas:

- Public Git credential-helper warning fidelity is covered by the later public source-git warning milestone.
- Annotation path/line target validation is covered by the later annotation target validation milestone.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Docker Platform Native Fallback Coverage

Implemented:

- Locked in Docker per-architecture capability behavior for `linux/amd64` and `linux/arm64` when Buildx platform reporting is unavailable.
- Docker capability probing already derives a supported platform from Docker info's native Linux architecture; the new coverage verifies `aarch64` normalizes to `linux/arm64`.
- The same coverage verifies the non-native configured platform remains `unsupported` when Buildx does not report it.
- This closes the top-level Docker platform specificity gap; remaining Docker work should be real-environment hardening beyond the local fake-Docker contract suite.

Known incomplete areas:

- Mutable-scope run enforcement is covered by the following progress entry.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_runner_docker.py -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Annotation Path And Line Target Validation

Implemented:

- `annotate add --target path:...` now verifies that the normalized repo path exists at the resolved commit as a Git blob or tree before storing the annotation.
- `annotate add --target lines:...` now verifies that the normalized repo path exists at the resolved commit as a Git blob.
- Line annotations now reject inclusive ranges whose end line exceeds the captured file contents at the resolved commit.
- Current-experiment shorthand still requires a clean worktree and stores the concrete HEAD commit, but now also validates the target path against the project repository.
- Expanded smoke coverage for successful path/line annotations, missing path rejection, missing line-target rejection, and out-of-range line rejection.
- Updated observe collaboration specs, README status, and local agent/core guides.

Known incomplete areas:

- Public Git credential-helper warning fidelity is covered by the later public source-git warning milestone.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Public Source Git Credential Warning

Implemented:

- `--source-git` clone and checkout now run with Git terminal prompts disabled through `GIT_TERMINAL_PROMPT=0` and Git Credential Manager interactive prompts disabled through `GCM_INTERACTIVE=never`.
- Public no-key inline `exp create --source-git` now detects configured local Git credential helpers and renders `PUBLIC_GIT_CREDENTIAL_HELPER_USED` when a helper is available.
- The same warning is stored in the imported source origin metadata so deduped or later source inspection can retain why the public import warned.
- `exp create` result blocks now include repeated `warning` fields for inline source import warnings; empty warning lists remain omitted by the renderer.
- Expanded smoke coverage with an isolated Git global config containing `credential.helper=store`, verifying public source-git warning output and persisted origin metadata.
- Updated CLI docs, README status, and local agent/core guides.

Known incomplete areas:

- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_public_exp_create_inline_source_import -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Experiment Branch Ref Deletion

Implemented:

- `exp remove --cascade` now resolves and renders the canonical experiment branch ref during dry-run.
- Actual experiment remove deletes the experiment branch ref after filesystem staging and before DB/audit mutation.
- If branch deletion succeeds but a later DB/audit mutation fails, ALab best-effort restores the branch ref to its previous commit before restoring staged filesystem paths.
- Experiment remove audit metadata now records the branch ref, previous branch commit, whether the ref was deleted, and whether it was already absent.
- Added smoke coverage that verifies the experiment branch ref exists before removal, is absent after removal, and is reflected in command output and audit metadata.

Known incomplete areas:

- Annotation standalone remove revision-count audit is covered in a later progress entry; standalone artifact/log remove is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Artifact And Log Reference-Counted Trash

Implemented:

- Standalone `artifacts remove` and `logs remove` now compute filesystem targets before DB/audit mutation.
- Captured artifact blobs are staged through ALab trash only when no remaining artifact row references the same blob path.
- Log files are staged through ALab trash only when no remaining log row references the same file path.
- Dry-run output reports `deleted filesystem paths`, affected filesystem paths, and planned trash moves.
- Actual remove records sanitized trash metadata and reports pending trash cleanup if immediate deletion fails.
- Added smoke coverage for a shared artifact blob across two runs and for a standalone log file removal.

Known incomplete areas:

- Annotation standalone remove revision-count audit is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Run Remove Cascade Trash Staging

Implemented:

- `runs remove` now blocks archived runs with dependent artifact or log rows unless `--cascade` is supplied.
- `runs remove --cascade` now blocks active dependent artifact/log rows and deletes archived dependent artifact/log rows in the same audited operation as the run row.
- Dependent captured artifact blobs and log files use the reference-counted trash staging path before DB mutation, so shared files are retained and unshared files are moved through ALab trash.
- Removing a latest run recomputes experiment latest run/commit from remaining runs; removing a final run preserves the closed submission while setting `final_run_removed_at`, `final_run_removed_by`, and `final_run_removed_audit_id`.
- Dry-run and actual output now report deleted artifact/log counts, active dependent counts, latest before/after, final-run removal, filesystem target count, planned trash moves, and pending trash cleanup.
- Audit metadata records dependent counts, active dependent counts, latest before/after, final-run removal, sanitized trash labels, target object ids, absent count, and path hashes without raw filesystem paths.
- Added smoke coverage for non-cascade blockers, active-child cascade blockers, cascade dry-run, final-run removal metadata, dependent row deletion, submission retention, latest recomputation/retention, and artifact/log file trash cleanup.

Known incomplete areas:

- Annotation standalone remove revision-count audit is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Validation Remove Reference-Counted Trash

Implemented:

- `project validation remove` now blocks dependent artifact/log rows unless `--cascade` is supplied.
- `project validation remove --cascade` blocks active dependent artifact/log rows and deletes archived dependent rows in the same audited operation as the validation row.
- Dependent captured artifact blobs and log files use the reference-counted trash staging path before DB mutation, so shared validation/run blobs are retained and unshared files are moved through ALab trash.
- Dry-run and actual output now report deleted artifact/log counts, active dependent counts, filesystem target count, planned trash moves, and pending trash cleanup.
- Audit metadata records dependent counts, active dependent counts, sanitized trash labels, target object ids, absent count, and path hashes without raw filesystem paths.
- Expanded smoke coverage for non-cascade blockers, active-child cascade blockers, shared artifact retention, log file trash cleanup, dependent row deletion, and validation audit metadata.

Known incomplete areas:

- Annotation standalone remove revision-count audit is covered in a later progress entry.
- Cross-device same-parent fallback is implemented in the staging helper but is not yet covered by a filesystem-level integration test.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`

## 2026-05-19 Capability Surface Hardening

Implemented:

- Replaced the coarse CLI help/preflight availability check with context-sensitive command surfaces for global, project-public, experiment-token, inspection-token, explicit-admin, and explicit-root callers.
- Public project contexts now expose only safe status plus public experiment creation when the active valid project config allows it.
- Experiment token contexts now expose run/submit, visible observe/read/export surfaces, token-owned lifecycle archive/unarchive operations, tags, annotations, and self inspection checkout creation without exposing project/source/config/key/cache/audit maintenance commands.
- Inspection token contexts now expose only status, read/export observe surfaces, and matching inspection checkout removal; mutation commands such as run, submit, tags, annotations, and run/archive lifecycle are blocked at capability preflight.
- Ambient `ALAB_KEY` no longer broadens help or public/token command surfaces. Root/admin commands require an explicit `--key` or `--key-stdin` to become available at preflight.
- Added smoke coverage for project, experiment, inspection, explicit-admin, and ambient-key help/preflight behavior.

Known incomplete areas:

- The broader golden CLI matrix in `docs/spec_tests.md` still needs systematic command-by-command coverage for field order, aliases, errors, and nested help.
- Remaining runner hardening should still focus on real Docker/Harbor/SkyDiscover environments beyond the local fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`

## 2026-05-18 Docker Unavailable And Real Runner Entry

Implemented:

- Added CLI-level coverage for Docker unavailable baseline behavior: Docker-backed `project init` now remains covered as a saved validation `error` record with project status `invalid` and exit `1`, rather than surfacing an internal error or writing a valid project.
- The unavailable-Docker test verifies the validation row, record failure reason, stderr log stream, and absence of an active valid config version.
- Added an opt-in `real_docker` pytest marker and `tests/test_real_docker.py` entrypoint. The test is skipped by default and runs only with `ALAB_RUN_REAL_DOCKER=1`.
- The real Docker test validates the Docker runner's actual `/app` and `/logs/alab` mounts, container-visible ALab env values, no-network mode, and stdout reward parsing against an Alpine container when Docker and the image are available.
- README and test spec now document the opt-in real Docker command.

Known incomplete areas:

- Real Harbor and SkyDiscover Docker environment validation still needs equivalent opt-in coverage.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_runner_docker.py`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_real_docker.py`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`

## 2026-05-18 Observe Contract Hardening

Implemented:

- `exp search` now applies the same `--reward-min` and `--reward-max` filters as experiment list/best.
- Experiment `--sort reward:asc` now keeps experiments without parsed reward values after concrete reward values, matching the documented null-last sort rule.
- Experiment search now includes latest annotation bodies only when the annotation itself is visible to the caller, so private annotations do not influence peer-token search results.
- Token-only log observe commands now reject `--include-hidden` immediately with `SCOPE_VIOLATION`, even when the selected visible rows are not hidden.
- Artifact and log export now require an existing parent directory instead of creating missing parent directories.
- Expanded smoke coverage for reward-filtered search, reward null-last sorting, private annotation search visibility, token hidden-log option rejection, and missing export parents.

Known incomplete areas:

- Remaining hardening should focus on real Docker/Harbor/SkyDiscover environments beyond the local fake-adapter suites.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Mutable Scope Run Enforcement

Implemented:

- `exp create` now records experiment mutable overrides from repeated `--mutable-include` and `--mutable-exclude` options.
- `alab run` now verifies the worktree is on the registered experiment branch and rejects in-progress Git operation states before staging.
- `alab run` now checks dirty staged/unstaged/untracked changes and the full baseline-to-HEAD diff against the intersection of the bound project mutable policy and the experiment override.
- `.alab/**` context/token files are ignored for mutable dirty checks and are still never staged into runner commits.
- Out-of-scope changes fail with `SCOPE_VIOLATION` before runner execution, preserving the worktree changes for the caller.
- Mutable path collection now enables Git rename/copy detection and validates both source and destination paths when Git reports `R*` or `C*` status entries.
- Manual commits whose full baseline-to-HEAD diff violates mutable scope now create a saved `runs.status = error` record with `mutable_scope.error_code = SCOPE_VIOLATION`, violation paths, and no runner execution, while leaving HEAD and the worktree unchanged.
- Expanded smoke coverage for experiment mutable override narrowing: a blocked dirty `README.md` change is preserved, an allowed `src/**` change creates an ALab run commit and passes, rename/copy edge cases reject out-of-scope paths, and a blocked manual commit is saved as a run error record.
- Added invalid Git state smoke coverage for detached HEAD, running on a non-registered branch, and an in-progress merge marker.

Known incomplete areas:

- Remaining runner hardening should focus on real Docker/Harbor/SkyDiscover environments beyond the local fake-adapter suites.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_run_rejects_invalid_git_states -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Annotation Remove Revision Audit

Implemented:

- `annotate remove` dry-run now reports the number of annotation revisions that would be deleted and explicitly reports zero filesystem targets.
- Actual annotation remove writes audit metadata with `deleted_revision_count`, zero filesystem targets, zero absent paths, and an empty trash list.
- Actual annotation remove now renders deleted revision count, zero deleted filesystem paths, and `trash cleanup pending: false`.
- Expanded smoke coverage for removing a private annotation after worktree token regeneration, verifying revision deletion, annotation row deletion, output fields, and audit metadata.

Known incomplete areas:

- Observe list filter/sort surfaces are covered by the later observe sort whitelist milestone.
- Public Git credential-helper warning fidelity is covered by the later public source-git warning milestone.
- Annotation path/line target validation is covered by the later annotation target validation milestone.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Best Incomparable Warning

Implemented:

- `exp best` and `observe experiments best` now aggregate runs excluded because their bound reward policy identity differs from the current comparable reward policy identity.
- When incompatible runs are excluded, `best` renders an `object: warning` block with `warning code: BEST_INCOMPARABLE_RUNS_EXCLUDED`, stable warning reason, and `excluded count`.
- Explicit `--config-version` best ranking remains unaffected because it compares only that config version.
- Expanded smoke coverage by changing the project reward direction after two runs, adding a new compatible run, and verifying the warning count for the two incompatible older runs.

Known incomplete areas:

- Observe list filter/sort surfaces are covered by the later observe sort whitelist milestone.
- Public Git credential-helper warning fidelity is covered by the later public source-git warning milestone.
- Annotation path/line target validation is covered by the later annotation target validation milestone.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Context Self-Repair Git Checks

Implemented:

- Self-token `context repair --path <dir>` now verifies that the target path is a Git worktree whose common Git directory is the ALab project repository.
- Worktree self-repair now requires the target checkout to be on the experiment's registered `experiments.branch_name`.
- Inspection self-repair now requires the target checkout HEAD commit to match the pinned inspection commit from the marker.
- Existing self-token safety gates remain in place: the old registered realpath must be absent, marker `token_id` must match the verified token credential, and the target realpath must not already be registered.
- Added smoke coverage that moves an experiment worktree with `git worktree move`, verifies detached-HEAD self-repair is rejected, then verifies repair succeeds after checking out the registered branch.

Known incomplete areas:

- Observe list filter/sort surfaces are covered by the later observe sort whitelist milestone.
- Public Git credential-helper warning fidelity is covered by the later public source-git warning milestone.
- Annotation path/line target validation is covered by the later annotation target validation milestone.
- Deeper Docker platform specificity remains pending.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Run Output Summary Hardening

Implemented:

- `_run_experiment` now returns a structured execution summary instead of a positional tuple.
- Top-level `alab run` output now renders the actual created-commit boolean, stdout/stderr previews, captured artifact count, and runner warning codes from the stored run execution.
- `alab run` output now matches the observable run record for artifact counts and runner warnings such as `ENV_MODE_FULL_UNREDACTED_HOST_ENV`.
- Expanded smoke coverage for the local run/observe workflow to assert top-level run artifact count, multiline stdout preview rendering, and warning-code parity with `runs list`.

Known incomplete areas:

- Mutable-scope run enforcement is covered by the following progress entry.

Verification:

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`

## 2026-05-19 CLI Contract And Context Path Hardening

Implemented:

- Tightened global option pre-scan so `--key-stdin` followed later by `--key` now fails with `CONFIG_INVALID`, matching the bidirectional conflict contract.
- Added CLI contract smoke coverage for `--key-stdin` conflicts and standalone `--` global-option stop behavior.
- Updated inspection checkout authorization so experiment tokens may create inspection checkouts for any token-visible experiment, not only their own experiment.
- Added shared context path validation for experiment worktree creation, worktree restore, and inspection checkout creation.
- New context paths must now be missing or empty, must not reuse an active registered path, may nest only under the same project's marker-only project control context, and cannot be created inside experiment or inspection contexts.
- Tightened `project secret gc` to require exactly one of `--dry-run` or `--apply`, preventing accidental apply semantics when both flags are present.
- Expanded smoke coverage for visible peer inspection checkout, rejected default nested experiment creation from an experiment context, and strict secret-GC selector handling.

Known incomplete areas:

- Stale `running` run/validation interruption semantics and the full golden CLI matrix still need broader coverage.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path -q`

## 2026-05-19 Stale Running Record Interruption

Implemented:

- Added a shared stale-record interruption helper for saved `runs.status = 'running'` and `project_validations.status = 'running'` rows left behind by interrupted ALab processes.
- Later status, run, submit, project validation, validation lifecycle, and run lifecycle archive/remove paths now mark matching stale running rows as `interrupted` before continuing.
- Interrupted run and validation records retain their original row ids and receive sanitized record metadata with `interrupted = true` and a stable failure reason.
- Interrupted validations also update matching running `project_config_versions.validation_status` values to `interrupted`.
- When the interrupted validation belongs to the latest attempted project config, the project becomes `invalid` and active validation/config pointers are cleared, matching the rule that skipped/interrupted baselines do not prove a runnable project.
- Added smoke coverage that injects stale running run and validation rows, runs `status`, and verifies run, validation, config, and project state reconciliation.

Known incomplete areas:

- Stale interruption is covered at the service/CLI level; lock ownership and heartbeat replacement semantics still need deeper tests around real concurrent operations.
- The full golden CLI matrix remains broader than the current smoke coverage.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`

## 2026-05-19 Nested Help And Secret Input Contract

Implemented:

- Tightened top-level help parsing so `alab help` and `alab --help` accept only the documented `--all` and `--explain` options; unknown or duplicate help options now fail with `CONFIG_INVALID`.
- Added command-level help selection for nested `--help` requests. The selected command's non-help arguments are passed into the same capability resolver used by execution preflight, so project-specific public availability such as `exp create --project <id> --help` matches direct invocation.
- Nested command help now renders the selected command row, including a locked row when the command exists but is not available in the current context, without entering the handler or reading value/body files.
- Added smoke coverage for `--output rich` being a per-command renderer selection that does not persist global config changes.
- Added smoke coverage for `project secret set --value-stdin` and `--value-file` rejecting empty values, embedded newlines, NUL bytes, values shorter than four UTF-8 bytes, and double trailing newlines after stripping at most one trailing newline.
- Added preflight coverage showing unavailable project secret mutation fails with `COMMAND_UNAVAILABLE` before reading a missing `--value-file`.

Known incomplete areas:

- The command-by-command golden output matrix in `docs/spec_tests.md` still needs broader field-order, alias, and error text coverage.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_project_secret_input_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source Origin Duplicate-Option Hardening

Implemented:

- Tightened shared source-origin parsing so repeated `--source-path`, `--source-git`, `--source-empty`, and `--source-ref` fail with `CONFIG_INVALID` and the precise duplicate-option message instead of a generic source-origin conflict.
- Preserved the existing `SOURCE_INVALID` behavior for truly multiple source origins and source selector scope conflicts such as `--source-subdir` without a path/Git source.
- Added smoke coverage for duplicate local source origins in `project init` and `source import`, duplicate `--source-empty`, and duplicate `--source-ref` in `exp create`, while preserving no-write failure assertions.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 From-Experiment Duplicate-Option Hardening

Implemented:

- Tightened `exp create --from-exp` so repeated `--from-exp` fails with `CONFIG_INVALID` and a precise duplicate-option message instead of the generic source-origin conflict.
- Preserved the existing source-origin conflict behavior for `--from-exp` combined with explicit source selectors, and preserved `--from-commit` duplicate validation.
- Updated from-experiment smoke coverage to assert no child experiment row, worktree, or add audit is created on duplicate `--from-exp`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Exact-One Pair Duplicate-Option Hardening

Implemented:

- Tightened the shared exact-one option-pair validator so repeated options fail with the precise `CONFIG_INVALID` duplicate-option message before the broader "requires exactly one of" relationship check.
- Applied the consistent duplicate-priority behavior across backup pruning, project secret value input, project secret GC, submit summary/feedback input, inspection checkout removal selectors, and annotation body input.
- Updated smoke coverage to preserve the existing missing/conflicting-pair errors while asserting duplicate-specific failures still happen before file reads, mutation writes, token/path revocation, and annotation revision writes.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Force/Confirm Duplicate-Option Hardening

Implemented:

- Tightened the shared force-confirm guard so repeated `--force` and `--confirm` fail with precise `CONFIG_INVALID` duplicate-option messages before the broader confirmation mismatch check.
- Preserved command-specific confirmation messages for missing `--force`, missing `--confirm`, and wrong confirmation values across destructive remove/catalog operations.
- Updated shared smoke helper coverage so all destructive confirmation guard call sites now assert duplicate-specific failures while retaining existing no-mutation checks in the surrounding tests.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Admin Annotation Private Target Hardening

Implemented:

- Tightened annotation privacy selection so root/admin callers cannot use bare `--private` and accidentally create a project-visible annotation.
- Root/admin private annotations must now use `--private-to-exp <exp_id>`, while experiment token callers keep the existing `--private` behavior bound to their own experiment identity.
- Added collaboration smoke coverage proving a project-context admin `annotate add --private` fails with `CONFIG_INVALID` before annotation or revision rows are written.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Public Invalid Status Hardening

Implemented:

- Tightened no-key public `status --project <id>` for invalid projects so it no longer renders task text or other project summary content.
- Invalid public status now renders only a safe public context block with project id, invalid status, and the documented admin/root validation next action.
- Added smoke coverage proving invalid public status omits task/project text while preserving the existing valid public status shape.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source Show Selector Conflict Hardening

Implemented:

- Tightened `source show` so a positional source selector and `--source-ref` cannot be provided together.
- Preserved valid source id/ref lookup behavior while rejecting ambiguous dual selectors with `CONFIG_INVALID` before source lookup.
- Added smoke coverage proving conflicting `source show <selector> --source-ref <ref>` inputs render a stable error block.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Experiment Query Duplicate-Option Hardening

Implemented:

- Added a shared experiment query duplicate-option guard for `exp list`, `exp search`, and `exp best`, covering filters, reward bounds, pagination, and supported sorting.
- Switched `exp list` project resolution to the same project-id helper used by other observe commands, so duplicate `--project` now fails with `CONFIG_INVALID`.
- Preserved repeated `--tag` AND semantics while adding smoke coverage for duplicate `--project`, time filter, reward bound, and pagination options across experiment list/search/best.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Observe List Filter Duplicate-Option Hardening

Implemented:

- Tightened `runs list`, `artifacts list`, and `logs list` duplicate-option validation to cover all documented filter options at command entry.
- Closed the `runs list` duplicate `--project` gap so repeated project selectors fail with `CONFIG_INVALID` instead of silently using the first value.
- Added smoke coverage for duplicate run-list `--project`, artifact-list `--run`, and log-list `--truncated` inputs alongside the existing duplicate sort/pagination coverage.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Observe List Duplicate Sort/Pagination Hardening

Implemented:

- Tightened `runs list`, `artifacts list`, and `logs list` duplicate-option validation so `--sort`, `--limit`, and `--offset` are rejected at command entry instead of after observe queries run.
- Kept valid observe sorting and pagination behavior unchanged while making duplicate sort/pagination errors consistent across run, artifact, log, and annotation list surfaces.
- Added smoke coverage for duplicate log and artifact list `--limit`/`--sort` attempts, alongside the existing run list duplicate coverage.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation List Duplicate Sort/Pagination Hardening

Implemented:

- Tightened `annotations list` duplicate-option validation to cover time filters, `--sort`, `--limit`, and `--offset` at command entry.
- Kept valid annotation list sorting and pagination unchanged while rejecting repeated sort/pagination options with `CONFIG_INVALID` before annotation queries and revision filtering.
- Added smoke coverage proving duplicate `--limit` and duplicate `--sort` attempts render stable error blocks.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation List Target Selector Hardening

Implemented:

- Tightened `annotations list` target filtering so `--target-id` and the compatibility `--target` selector cannot be provided together.
- Preserved valid annotation list filters while rejecting ambiguous target selector input with `CONFIG_INVALID` before any annotation query runs.
- Added smoke coverage proving conflicting annotation target selectors render a stable error block.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Audit List Duplicate-Option Hardening

Implemented:

- Tightened `audit list` duplicate-option validation to cover every accepted filter and pagination option, including `--actor`, `--created-after`, `--created-before`, `--limit`, and `--offset`.
- Kept audit query behavior unchanged for valid filters while ensuring repeated actor/time/pagination options fail with `CONFIG_INVALID` instead of silently using the first value.
- Added smoke coverage proving duplicate `--actor` and duplicate `--limit` attempts render stable error blocks.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Audit List No-Positional Argument Hardening

Implemented:

- Tightened `audit list` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Kept audit authorization and duplicate-filter validation priority, while rejecting extra positional arguments before audit event queries.
- Added smoke coverage proving `audit list` rejects extra positional arguments alongside valid `--object-type` and `--object-id` filters.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation Add/List No-Positional Argument Hardening

Implemented:

- Tightened `annotate add` and `annotations list` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Extended the shared positional parser to recognize annotation list filter values (`--target-type`, `--target-id`, and `--created-by`) while rejecting extra positional arguments before annotation body file reads, annotation row/revision writes, or annotation list queries.
- Added annotation smoke coverage proving extra positional add attempts preserve annotation/revision counts and fail before missing body-file reads, and that annotation list rejects the same grammar drift.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Text Limit And Lifecycle Reason Hardening

Implemented:

- Extended shared UTF-8 byte-limit validation to project config text fields, source display names, experiment names, tag slugs, and lifecycle remove reasons.
- Project init and project config mutation now reject empty or over-120-byte `project.name` / `task.description` values before they become persisted config versions.
- Source import display names and experiment names now reject empty or over-120-byte values.
- Experiment goal text now rejects values over 65536 bytes.
- Experiment tag creation, tag mutation, and tag filters now use one shared slug validator and reject tags whose normalized slug exceeds 64 bytes instead of silently truncating them.
- `exp create` now validates goal text, tag slugs, mutable overrides, and visibility overrides before source import or Git worktree creation, so invalid no-`--path` creates no longer leave default worktree directories in the caller's cwd.
- Lifecycle remove reason handling now uses one shared reader with the documented 65536-byte limit, so invalid reasons are rejected before dry-run rendering, destructive filesystem staging, trash finalization, DB mutation, or audit writes.
- SkyDiscover catalog remove now validates long reasons before deleting the registered catalog path.
- Added deterministic filesystem coverage for cross-device trash staging fallback by simulating an `EXDEV` home-trash rename failure, verifying same-parent `.alab-trash-<audit_id>` staging, cleanup of the unused home trash directory, and restore behavior.
- Added exact-boundary acceptance fixtures for 120-byte multibyte display names, 65536-byte multibyte project task/goal values, 65536-byte submit summary/feedback file inputs, 65536-byte annotation body file input, 300-byte run/submit messages, and 64-byte tag slugs.
- Expanded smoke coverage for project/source/experiment display-name limits, multibyte project/source/experiment display-name byte limits, multibyte project task/goal byte limits, experiment goal limits, tag limit rejection, failed `exp create` worktree cleanliness, multibyte run/submit message byte limits, multibyte submit summary/feedback byte limits, file-input submit summary/feedback byte limits, multibyte annotation-body byte limits, file-input annotation-body byte limits, lifecycle dry-run reason preflight, multibyte lifecycle reason byte limits, long catalog-remove reason preflight, and retained catalog state after failed reason validation.

Known incomplete areas:

- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_skydiscover_catalog_lifecycle -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Config And Archive Contract Coverage

Implemented:

- Tightened global `config set` so only documented fields can be edited, `output.format` remains limited to `"text"`, and numeric fields must be positive integers.
- Tightened global `config reset` so callers must pass exactly one documented field or `--all`; field reset now restores that field from the default config without rewriting unrelated values.
- `config set output.format "text"` can repair a parseable config whose persisted output format was accidentally changed away from the V1-compatible value.
- `config validate` now rejects manually edited global configs with invalid numeric fields instead of rendering them as valid.
- Added debug-mode coverage showing internal exceptions print a traceback only with `ALAB_DEBUG=1`, while normal output stays on the stable ALab error object.
- Expanded observe lifecycle coverage for archived log/artifact behavior: show by id still succeeds when authorized, while export requires `--include-archived`.
- Added project config validation coverage for rejected `runner.network = "host"`, invalid environment variable names, and direct `secret_env.*` mutation through `project config set`.

Known incomplete areas:

- Full command-by-command golden output fixtures remain broader than the current smoke suite.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_stack_trace_only_for_internal_errors tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Audit Filters And Token Selector Disclosure

Implemented:

- Added `help` as a registry-backed canonical command row so context-aware help output includes the documented help command itself.
- Updated `help --all` rendering to list available command rows before locked rows while preserving registry order within each group.
- Tightened `audit list --object-id` when paired with a known `--object-type`, validating ALab object-id prefixes for project/source/experiment/worktree/run/artifact/log/annotation/validation/credential/inspection-checkout filters and stable literals for catalog/cache/backup filters.
- Tightened `audit list --actor`, `--limit`, and `--offset` so invalid credential ids and non-integer pagination fail with `CONFIG_INVALID` instead of leaking through generic errors.
- Tightened `annotations list --target-id` for object-backed targets, requiring complete experiment/run/artifact ids when the matching target type is selected.
- Updated token-scoped observe and annotation selectors so missing or invisible experiments, runs, artifacts, logs, and annotations return non-disclosing `SCOPE_VIOLATION` reasons instead of precise `*_NOT_FOUND` details.
- Expanded smoke coverage for help row/order behavior, audit object-id and pagination validation, annotation target-id validation, and token not-visible-or-not-found selector behavior.

Known incomplete areas:

- Some generic audit object types still intentionally keep literal or legacy object ids because historical audit rows do not all use ALab object-id prefixes.
- The full golden CLI matrix still needs command-by-command field-order and alias coverage.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Time Filter And Object Selector Hardening

Implemented:

- Tightened RFC 3339 parsing so accepted time filters must use a `T` date/time separator and either `Z` or a numeric `+HH:MM`/`-HH:MM` offset.
- Updated `audit list --created-after/--created-before` to use the same RFC 3339 normalization path as observe and experiment time filters.
- Connected complete ALab object-id validation to user-facing selectors for projects, credentials, validations, sources, experiments, runs, artifacts, logs, annotations, audit events, inspection token selectors, and observe list filters.
- Source refs remain an explicit source-selector exception, and Git commit selectors remain separate from ALab object-id validation.
- Expanded smoke coverage for strict audit time filters, incomplete credential/source/run/log/artifact/annotation selectors, valid full-id behavior on the same command paths, and `OUTPUT_EXISTS`/`--overwrite` behavior for config, log, and artifact exports.

Known incomplete areas:

- Audit `--object-id` remains generic because it can refer to multiple object types; object-type-specific validation can be tightened once the audit filter matrix is covered command by command.
- The broader golden CLI matrix still needs systematic field-order and command-family error text coverage.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Saved Result Failure And Alias Contract Coverage

Implemented:

- Saved run failures now append stable result-failure fields after the normal run payload: `error code`, CLI `exit code`, `reason`, and `next`.
- Baseline validation failures rendered through `project init`, `project validate`, and runtime-affecting `project config set` now append `BASELINE_VALIDATION_FAILED` result-failure fields instead of relying only on inferred exit status.
- Project init now renders a validation next action when the initial baseline is not valid, while keeping the experiment-create next action for valid projects.
- Added debug-mode coverage proving saved failed runs do not print CLI tracebacks under `ALAB_DEBUG=1`; only internal/system failures do.
- Expanded alias coverage so `exp show`, `runs list`, `logs list`, `artifacts list`, `annotations list`, and `annotations show` are compared against their canonical `observe ...` command paths, including global `--home` placement after aliases.
- Added Docker-unavailable baseline coverage for the new `BASELINE_VALIDATION_FAILED` result fields.

Known incomplete areas:

- The complete CLI golden matrix still needs broader command-by-command field-order and error text fixtures.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit Result Failure Contract

Implemented:

- `submit` now validates summary, feedback, and refs before running the experiment runner, so invalid submit inputs cannot create saved run side effects.
- Summary and feedback now require exactly one direct text value or file input, matching the V1 CLI contract.
- Submit refs now use the shared repeated-option parser, dedupe refs in first-seen order, reject missing ref values, keep `--ref none` mutually exclusive with experiment refs, and validate experiment refs against the submitting token's visible experiment set.
- Submit summaries and feedback now reuse the active-secret body check before any submission text is stored.
- Missing reusable passed runs now return an `object: submission` result failure with `submit accepted: false`, `RUNNER_FAILED`, and the documented `--rerun` next action instead of a generic error block.
- `submit --rerun` final-run failures now keep the failed run record but return `submit accepted: false`, leave the experiment open, avoid writing a submission row, and append stable result-failure fields without printing debug tracebacks.
- Added smoke coverage for invalid submit input preflight, structured failed-submit output, retained failed run records, open experiment state, and missing reusable-run output.
- Expanded submit ref preflight coverage for trailing `--ref` without a value, `--ref` followed by another option, `--ref none` mixed with an experiment ref, invisible experiment refs, complete-but-missing experiment refs, and no-run side effects after all invalid ref cases.

Known incomplete areas:

- The complete CLI golden matrix still needs broader command-by-command fixtures.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit Input Limits And Visibility Override

Implemented:

- Added shared UTF-8 byte-limit validation for run messages, submit messages, submit summaries, submit feedback, and annotation bodies.
- `run --message` and `submit --message` now reject values over 300 bytes before runner execution.
- Submit summary and feedback now reject values over 65536 bytes, whether supplied directly or through files, before runner execution or submission storage.
- Submit summary and feedback secret-value rejection now renders field-specific errors instead of reusing the annotation-body reason.
- Annotation direct empty bodies now satisfy the documented exactly-one input rule because `--body ""` is treated as a provided value, not as a missing option.
- Experiment creation now honors `--visibility-scope` and `--visible-exp` by storing the intersection of the project visibility policy and the requested override as the experiment visibility upper bound.
- Added validation for invalid visibility override combinations: `--visible-exp` requires explicit visibility, non-explicit visibility rejects visible-exp ids, and explicit visibility requires at least one visible experiment id.
- Expanded smoke coverage for submit length limits, submit secret rejection, invisible submit refs, no-run side effects on invalid submit input, and narrowed experiment visibility.

Known incomplete areas:

- The complete CLI golden matrix still needs broader command-by-command fixtures.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Multiline Text Rendering Contract

Implemented:

- Added an explicit renderer value for multiline user text so scalar fields remain compact while task, goal, status task, and annotation body fields follow the documented text-output contract.
- Empty non-null multiline text now renders as a multiline field with `[empty]`, distinct from nullable `none` and the literal user text `none`.
- Project show, project config show, status, and annotation observe/show now use explicit multiline rendering for user-authored text fields.
- Expanded smoke coverage for renderer-level multiline/empty/nullable behavior and CLI annotation body rendering, including `--body ""`.

Known incomplete areas:

- The complete CLI golden matrix still needs broader command-by-command fixtures.
- Real Harbor and SkyDiscover Docker environment validation remains an opt-in hardening gap beyond the fake-adapter suites.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_text_renderer_object_block tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker-Backed Adapter Entry Points

Implemented:

- Expanded the opt-in `real_docker` pytest entrypoint so `ALAB_RUN_REAL_DOCKER=1` now covers the Docker runner, Harbor shared verifier execution, and SkyDiscover Docker evaluator execution.
- Added a real Harbor fixture that runs an Alpine verifier container, checks the candidate workspace and run directory mounts, writes `reward.json`, and verifies hidden verifier output capture.
- Added a real SkyDiscover Docker fixture that builds an Alpine evaluator image, runs the evaluator against the mounted candidate workspace with `network = "none"`, parses JSON metrics, and verifies hidden evaluator stderr capture.
- Kept all real Docker-backed tests skipped by default so the normal suite never pulls images unexpectedly.
- Updated README and README_cn setup guidance to describe the broader opt-in Docker-backed coverage.

Known incomplete areas:

- The complete CLI golden matrix still needs broader command-by-command fixtures.
- Real SkyDiscover Python dependency-installation validation can be added as a separate opt-in environment test if future hardening requires networked `uv` installs.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 CLI Golden Foundation Coverage

Implemented:

- Added shared smoke helpers for extracting rendered field-label order from strict text object blocks.
- Tightened `auth init`, `auth root regenerate`, `config show`, `config set`, and `config reset` coverage from loose substring checks to ordered field-label checks matching the CLI contract.
- Added root regeneration lifecycle coverage proving the old root key id is rendered as revoked and the old raw root key no longer authenticates.
- Tightened nested command help coverage so selected help output now checks both the `help` block field order and the `help_command` row field order, and confirms global help starts with the registry-backed `help` row.
- Added project public `status` and `project config show` field-order checks, including multiline task/goal output from actual CLI command paths.

Known incomplete areas:

- The complete CLI golden matrix still needs broader command-by-command fixtures beyond the initial auth/config/help foundation.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run Submit And Observe Golden Coverage

Implemented:

- Tightened the core local agent workflow from loose substring checks to ordered field-label checks for `exp create`, `run`, and successful `submit` output.
- Added ordered field-label checks for submit result-failure output so appended diagnostic fields remain stable after the normal submit summary fields.
- Added observe/list row order coverage for runs, logs, and artifacts, including hidden-log availability and warning-code placement.
- Fixed the smoke test capture boundary around archived log export so artifact-list assertions cannot be polluted by previous command output.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion beyond the current auth/config/help, project status/config, run/submit, and observe-list coverage.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Tag And Maintenance Golden Coverage

Implemented:

- Added ordered field-label coverage for project config mutation/export, secret GC, and stale-lock clearing outputs.
- Added ordered field-label coverage for source import/show/archive/unarchive outputs on the non-default source lifecycle path.
- Added ordered field-label coverage for experiment tag add/list/remove outputs.
- Documented through tests that empty list-valued fields are omitted from rendered text blocks, while non-empty tag lists still render in order.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across the remaining lifecycle remove, checkout/repair, audit, and search/best surfaces.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Audit Search And Best Golden Coverage

Implemented:

- Added shared experiment field-label expectations for `exp list`, `exp search`, `exp show`, and `exp best`/`observe experiments best` output blocks.
- Locked search privacy behavior to both content filtering and empty-output rendering when private annotation text is not visible to the current context.
- Added warning-block field-order coverage for incomparable best-run exclusions.
- Added ordered field-label coverage for `audit list` and `audit show`, including retained sanitized metadata placement.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across lifecycle remove, checkout/repair, token regeneration, and artifact/log show/export/archive surfaces.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Artifact And Log Operation Golden Coverage

Implemented:

- Added shared field-label expectations for log and artifact object blocks so list/show/export paths verify the same output contract.
- Tightened log export, overwrite export, archived show, archive, and include-archived export coverage from object-presence checks to ordered field-label checks.
- Tightened artifact export, overwrite export, archived show, archive, and include-archived export coverage from object-presence checks to ordered field-label checks.
- Added reusable archive-result field-label expectations for archive status transitions and audit id placement.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across lifecycle remove, checkout/repair, token regeneration, and unarchive/remove operation surfaces.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Context Token And Remove Golden Coverage

Implemented:

- Added ordered field-label coverage for context show and context repair, including self-token repair after a moved worktree returns to the registered branch.
- Added ordered field-label coverage for experiment token list and token regenerate outputs.
- Added ordered field-label coverage for inspection checkout create/remove and worktree remove/restore outputs, including dry-run versus destructive-result field differences.
- Added observe log/artifact unarchive output coverage.
- Added observe artifact/log/run remove dry-run and destructive-result field-order coverage, including blocker placement and repeated list labels for multi-path run removal plans.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across project/experiment whole-tree remove, validation remove/archive, annotation edit/archive/remove, and adapter-specific init surfaces.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Validation Annotation And Tree Remove Golden Coverage

Implemented:

- Added ordered field-label coverage for validation archive/unarchive and validation remove dry-run/destructive outputs, including blocker placement and repeated filesystem-path labels.
- Added ordered field-label coverage for annotation edit, archive, and remove dry-run/destructive outputs.
- Added ordered field-label coverage for experiment archive and whole-experiment remove dry-run/destructive outputs, including branch-ref and filesystem-removal fields.
- Added ordered field-label coverage for project archive and whole-project remove dry-run/destructive outputs.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across adapter-specific init surfaces, source list/remove, cache/backup prune, key list/revoke, and project/experiment unarchive variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Key Cache And Unarchive Golden Coverage

Implemented:

- Added ordered field-label coverage for root/admin key list and key revoke outputs.
- Added ordered field-label coverage for backup prune and cache prune outputs, including repeated list labels for pruned backup paths and selected cache kinds.
- Added ordered field-label coverage for source list and source remove dry-run/destructive outputs on the removable non-default source lifecycle path.
- Reused the source status helper for source archive/unarchive output checks.
- Added project and experiment unarchive output coverage before re-archiving for whole-tree removal tests.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across adapter-specific init surfaces, source warning variants, project init result variants, and runner adapter result blocks.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Adapter Init And Source Warning Golden Coverage

Implemented:

- Added ordered field-label coverage for SkyDiscover catalog add/show/update/remove outputs.
- Added ordered field-label coverage for adapter-referenced project init outputs across SkyDiscover catalog validation, SkyDiscover Python/Docker baseline runs, Harbor baseline runs, Harbor-derived source init, and SkyDiscover initial-program init.
- Added reusable project init, experiment create, source import, and SkyDiscover catalog field-label helpers for the CLI golden matrix.
- Added ordered field-label coverage for experiment create outputs with and without inline-source warning rows.
- Added ordered field-label coverage for source import warning variants, including tracked sensitive source files and empty-after-filter imports.

Known incomplete areas:

- The complete CLI golden matrix still needs command-by-command fixture expansion across remaining runner adapter result blocks and less common config/source edge cases.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_harbor_project_init_uses_declared_source_and_excludes_private_assets tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules tests/test_smoke.py::test_source_import_empty_after_filter_warns -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Runner Adapter Result Golden Coverage

Implemented:

- Added a reusable ordered field-label helper for CLI `run` outputs, including optional warning-code rows and failure-field suffixes.
- Reused the helper in the core local workflow and host-env warning workflow so passed runs and warning-bearing runs share one output contract.
- Extended the SkyDiscover Python baseline smoke test through experiment create and CLI `run`, verifying the adapter run result block and parsed reward output.
- Extended the SkyDiscover Docker fake-adapter smoke test through experiment create and CLI `run`, verifying the adapter run result block and parsed reward output.
- Extended the Harbor fake-adapter smoke test through experiment create and CLI `run`, verifying the adapter run result block and parsed reward output.

Known incomplete areas:

- The complete CLI golden matrix still needs smaller command-by-command fixture expansion across less common config/source edge cases and failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Failure And Edge Result Golden Coverage

Implemented:

- Added reusable ordered field-label helpers for CLI error blocks, project config set results, project validation results, and submission failure results.
- Added ordered field-label coverage for debug-safe saved run failures so persisted `RUNNER_FAILED` output keeps the normal run summary followed by failure fields.
- Added ordered field-label coverage for submission failure result blocks, including rerun failure and missing reusable passed-run failure.
- Added ordered field-label coverage for mutable-scope recorded run errors and normal mutable-scope passed runs.
- Added ordered field-label coverage for representative CLI error blocks and exact-boundary success outputs for project init, source import, experiment create, and manual project validate.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_stack_trace_only_for_internal_errors tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker Environment Probe

Implemented:

- Probed the current real Docker environment before running opt-in integration coverage.
- Confirmed the Docker CLI is installed, but the configured Docker Desktop daemon socket is unavailable in the current session.
- Ran the opt-in real Docker pytest entrypoint with `ALAB_RUN_REAL_DOCKER=1`; all three real Docker tests skipped cleanly because the daemon is unavailable, rather than failing.

Known incomplete areas:

- Real Docker runner, Harbor verifier, and SkyDiscover Docker evaluator execution still need to be rerun in an environment with a running Docker daemon.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `docker version`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py -q`

## 2026-05-19 Baseline Failure Result Golden Coverage

Implemented:

- Added ordered field-label coverage for project init baseline failures, including the project result summary followed by `BASELINE_VALIDATION_FAILED` fields.
- Added ordered field-label coverage for manual project validation failures on an invalid project.
- Added ordered field-label coverage for runtime-affecting project config set failures and the subsequent successful recovery config set.
- Extended representative stderr error-block coverage to old root-key auth denial, command unavailability, context conflict, output-exists export errors, and private-safe not-found scope violations.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real Docker runner, Harbor verifier, and SkyDiscover Docker evaluator execution still need to be rerun in an environment with a running Docker daemon.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Annotation Collaboration Golden Coverage

Implemented:

- Added reusable ordered field-label helpers for annotation add outputs and full annotation observe/show/list blocks.
- Added ordered field-label coverage for path-target, line-target, experiment-target, and private annotation creation outputs.
- Added ordered field-label coverage for filtered annotation list output and multi-block sorted annotation list output.
- Added ordered field-label coverage for annotation show with history, including repeated revision rows, and for empty-body annotation show output.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real Docker runner, Harbor verifier, and SkyDiscover Docker evaluator execution still need to be rerun in an environment with a running Docker daemon.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker Integration Validation

Implemented:

- Re-ran the opt-in real Docker integration suite after Docker Desktop was started and confirmed the daemon is reachable.
- Fixed the real Docker test harness to isolate Docker client state with a temporary `DOCKER_CONFIG` when the environment does not already provide one, avoiding sandbox writes to the user's default `~/.docker/buildx/activity` path.
- Verified the real Docker runner path with an Alpine container, mounted workspace/run directories, and parsed stdout reward.
- Verified the real Harbor shared verifier path with an Alpine verifier container, hidden verifier logs, reward file parsing, and metrics parsing.
- Verified the real SkyDiscover Docker evaluator path with an Alpine evaluator image build, read-only evaluator mount, hidden stderr capture, JSON metric parsing, and reward extraction.

Known incomplete areas:

- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.
- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.

Verification:

- `docker version`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker CLI Workflow Validation

Implemented:

- Added opt-in real Docker CLI workflow coverage that creates a project with a real Docker runner, runs baseline validation through `project init`, creates an experiment, and executes `alab run` from the experiment worktree.
- Verified the real Docker CLI path writes run logs, captures a `run:` artifact produced inside the container, stores the run reward, and stores the baseline validation reward in SQLite.
- Verified top-level CLI run output for the real Docker path, including parsed reward, captured artifact count, and `DOCKER_SETUP_OUTPUT_CAPTURED` warning propagation.
- Kept the test under the `real_docker` marker and `ALAB_RUN_REAL_DOCKER=1` guard so normal test runs still skip external Docker execution.

Known incomplete areas:

- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.
- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.

Verification:

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py::test_real_docker_cli_project_run_workflow -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 SQLite Migration File And Backup Hardening

Implemented:

- Added file-backed SQL migration loading from `src/alab/migrations/`, starting with `1_initial.sql` generated from the existing V1 schema.
- Removed the previous duplicate embedded schema from `db.py`; runtime schema DDL now lives only in migration SQL files.
- `Database.migrate()` now validates migration filenames, contiguous schema versions, exact `sha256:<hex>` checksums, unknown applied versions, checksum/name mismatches, and newer-on-disk schema versions before normal storage access.
- Migration application now uses an ALAB_HOME-level file lock, applies each pending migration as a single SQL transaction, and records exact migration metadata in `schema_migrations`.
- Before applying a pending migration to an existing migrated database, ALab now creates a consistent SQLite backup through the SQLite backup API under `ALAB_HOME/backups/alab-<from>-to-<to>-<timestamp>.db`.
- Added focused migration tests for exact file checksum recording, checksum mismatch rejection, pre-upgrade backup creation before a simulated future migration, failed-version rollback, and downgrade rejection.
- Added setuptools package data for `alab/migrations/*.sql` and verified the built sdist/wheel include `alab/migrations/1_initial.sql`.
- Updated project license metadata to the SPDX string form to remove the setuptools deprecation warning during builds.
- Updated README and local agent guides to mention file-backed migration checksum validation and pre-upgrade backups.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv build`
- `git diff --check`

## 2026-05-19 Path Hash Case Normalization

Implemented:

- Added filesystem-aware path hash normalization so path registry hashes casefold resolved realpaths only when the underlying filesystem is detected as case-insensitive.
- The detection path uses existing path components and `samefile` checks, avoiding writes during normal path hashing.
- Added focused tests proving path hashes collapse case variants on case-insensitive filesystems and preserve case distinctions on case-sensitive filesystems.
- Updated README status text to document the case-normalized path registry behavior.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv build`
- `git diff --check`

## 2026-05-19 Public Id Contract Coverage

Implemented:

- Added focused tests for public object id suffix generation, locking the documented 22-character unpadded base64url encoding of 128 bits of entropy.
- Added tests for `new_id` slug/suffix composition and `require_complete_id` rejection of incomplete, padded, too-short, and too-long suffix variants.
- Added slug normalization coverage for NFKC input and fallback slugs.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_ids.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Storage Invariant Coverage

Implemented:

- Added focused storage tests proving ALab SQLite connections use WAL journal mode after migration.
- Added canonical JSON ordering coverage for nested dictionaries, compact separators, and non-ASCII preservation.
- Added config hash stability coverage showing semantically identical dictionaries with different insertion order produce the same `sha256:<hex>` hash.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Capability Preflight File-Input Guard Coverage

Implemented:

- Added inspection-context golden coverage proving unavailable `submit` commands fail with `COMMAND_UNAVAILABLE` before reading missing `--summary-file` or `--feedback-file` paths.
- Added inspection-context golden coverage proving unavailable `annotate add` commands fail with `COMMAND_UNAVAILABLE` before reading a missing `--body-file` path.
- Extended the existing capability help/preflight scenario to cover body/summary/feedback file inputs in addition to the previously covered project secret value file path.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Option Sentinel Coverage

Implemented:

- Added CLI golden coverage proving global pre-scan stops at standalone `--` before `--key-stdin`, so the token is treated as a command argument and stdin is not read.
- Kept this in the existing global-option edge scenario alongside post-command global option placement, global-output selection, and key conflict checks.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Error Exit Mapping Contract Coverage

Implemented:

- Added focused tests locking every registered `*_NOT_FOUND` code to exit `2`.
- Added focused tests locking `PROJECT_INVALID` and `COMMAND_UNAVAILABLE` to exit `4`.
- Added focused tests locking runner/reward/baseline result-failure codes to exit `1`, `OUTPUT_EXISTS` to exit `2`, and unknown internal errors to default exit `5`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_errors.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Credential Storage Contract Coverage

Implemented:

- Added focused credential storage tests proving raw admin credentials and raw secrets are not stored in credential metadata, salts, or verifier hashes.
- Added coverage that raw credential wire format embeds the generated credential id and remains parseable by credential type.
- Added verification tests for required credential scope, project binding, token mode binding, token path binding, and revoked-token rejection.
- Added DDL coverage for the one-active-root partial uniqueness constraint.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 DDL And Path Registry Contract Coverage

Implemented:

- Added representative SQLite enum `CHECK` coverage for credentials, audit events, runs, and path registry rows.
- Added required index presence coverage for critical audit, credential, project, config, source, experiment, run, artifact, log, annotation, path registry, lock, and cache lookup indexes.
- Added path registry partial-unique coverage proving removed rows do not block path reuse while duplicate active path/hash rows remain rejected.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Migration Lock Contract Coverage

Implemented:

- Added an interprocess migration test proving `Database.migrate()` blocks on the ALAB_HOME `.migration.lock` file while another process holds the lock.
- Verified the blocked child process does not create the SQLite database before the lock is released, then completes migration after release.
- Locked the migration-lock behavior with the existing migration checksum, backup, rollback, downgrade, WAL, DDL, and path-registry tests.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Worktree Token Uniqueness Coverage

Implemented:

- Added focused credential DDL coverage proving only one active worktree token can exist for an experiment.
- Verified revoked worktree token history does not block creation of a replacement active worktree token.
- Verified multiple active inspection tokens for the same experiment are not blocked by the worktree-token partial unique index.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Migration File Validation Coverage

Implemented:

- Added focused migration tests rejecting `.sql` files whose names do not match the `<version>_<name>.sql` contract.
- Added focused migration tests rejecting non-contiguous migration version sets before any database migration is applied.
- Extended the migration contract coverage alongside checksum mismatch, downgrade rejection, per-version rollback, pre-upgrade backups, and home-level migration locking.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Text Renderer List And Null Contract Coverage

Implemented:

- Extended the renderer golden test to prove list fields render as repeated labels rather than comma-separated scalar fields.
- Added coverage distinguishing nullable multiline fields (`field: none`), empty user text (`[empty]`), and literal user text `none` rendered as an indented multiline value.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_text_renderer_object_block -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Secret Fingerprint And Retain Marker Coverage

Implemented:

- Extended project secret CLI coverage to verify plaintext local `secret_values.value` storage while command output, secret list, config show, and config export never render the raw secret value.
- Added fingerprint checks proving the stored HMAC fingerprint is generated from the project fingerprint key and binds both the `secret_env` name and value.
- Added config export/import coverage proving exported retain markers contain only retain metadata plus fingerprint, and cannot be reused under a different `secret_env` name.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Named DDL Table And Column Coverage

Implemented:

- Added schema-introspection tests for V1-named storage surfaces: `experiment_submissions`, `experiment_tags`, `runtime_capabilities`, `catalogs`, and `cache_entries`.
- Added column coverage for `projects.secret_fingerprint_key`, `experiments.bound_validation_id`, final-run removal metadata, validation archive columns, and `annotations.target_json`.
- Kept this alongside existing DDL enum, index, migration, path registry, and token uniqueness coverage.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Config Version No-Op And Inheritance Coverage

Implemented:

- Extended project config lifecycle coverage proving repeated no-op `project config set` operations do not create additional config versions.
- Added metadata-only config edit coverage proving a new `inherited` config version is created, `active_valid_config_version` advances to it, and `active_validation_id` remains the validation that proved the unchanged runtime config.
- Added revert coverage proving returning to older canonical config content creates a new monotonic version with a duplicate `config_hash`, so config hashes are not uniquely constrained.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Config Dry-Run No-Write Coverage

Implemented:

- Added project config dry-run coverage using runner commands that would fail if executed.
- Verified both `project config set --dry-run` and `project config import --dry-run` report `validation status: dry-run` and keep `latest_attempted_config_version`, `active_valid_config_version`, and `active_validation_id` unchanged.
- Verified dry-run config set/import changes do not add `project_config_versions`, `project_validations`, or lifecycle `audit_events` rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run Nullable Field DDL Coverage

Implemented:

- Added storage DDL coverage proving `running`, `error`, and `interrupted` run rows can be stored with null `exit_code`, `reward_value`, and `ended_at`.
- Kept this alongside the existing run enum checks, archive status checks, run index coverage, and run lifecycle smoke tests.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Secret GC Candidate And Audit Coverage

Implemented:

- Extended project secret coverage with an explicit unreferenced local secret value to verify GC candidate calculation.
- Verified `project secret gc --dry-run` reports the candidate without rendering the raw secret value, deleting rows, or writing audit events.
- Verified `project secret gc --apply` deletes only the unreferenced secret value, preserves the referenced active secret, and writes a `gc` audit event for `secret_value`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Remove Dependency Coverage

Implemented:

- Completed `source remove` lifecycle enforcement for dependent experiments.
- `source remove` now blocks on dependent experiments unless `--cascade` is supplied, and `--cascade` still requires every dependent experiment to be archived.
- Source removal now deletes the corresponding Git source ref and restores it if the database update fails.
- Extended smoke coverage to verify dependent experiments are retained, archived dependency requirements are enforced, and the removed source ref is absent from the project repository.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit State Gate Coverage

Implemented:

- Added explicit `submit` state checks matching the V1 contract: the project must not be archived, the experiment must be open, and the experiment worktree state must be active.
- Closed a reusable passed-run bypass where `submit` could avoid `_run_experiment()` and therefore skip those state checks.
- Extended the local run/submit smoke workflow to verify `PROJECT_ARCHIVED`, `SCOPE_VIOLATION` for removed worktree state, and `EXPERIMENT_CLOSED` before accepting a reusable passed run.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Project Exp Create Error Code

Implemented:

- Adjusted `exp create` so an archived project fails with `PROJECT_ARCHIVED` instead of the generic `PROJECT_INVALID`.
- Added smoke coverage for the explicit admin-key path, which reaches the handler after capability preflight and verifies the documented archived-project error code.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Stale Lock Clear Positive Coverage

Implemented:

- Extended `project locks clear-stale` smoke coverage with one expired lock and one live lock in the same project.
- Verified the command reports only the expired lock name, deletes only the expired lock row, preserves the live lock row, and writes a `clear` audit event for `lock` with `cleared_count`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Target Not Archived Blocker Contract

Implemented:

- Aligned hard-remove dry-run and actual-remove blockers with the lifecycle contract by using the stable `target_not_archived` blocker instead of object-specific `project_not_archived`, `source_not_archived`, `experiment_not_archived`, `run_not_archived`, `artifact_not_archived`, `log_not_archived`, `validation_not_archived`, or `annotation_not_archived` names.
- Extended smoke coverage across source, run, artifact, log, annotation, experiment, and project remove dry-runs to verify active targets render `target_not_archived`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Remove Cascade Argument Contract

Implemented:

- Enforced the documented `project remove` requirement that `--cascade` is mandatory for both dry-run and actual removal.
- Kept `--reason` validation ahead of the cascade check so oversized reason text still fails with the text-size `CONFIG_INVALID` path.
- Added smoke coverage proving `project remove --dry-run` without `--cascade` fails with `CONFIG_INVALID` and the stable cascade-required message.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hard Remove Confirmation Guard Coverage

Implemented:

- Added a shared smoke-test assertion for destructive remove confirmation guards.
- Extended coverage for missing `--force`, missing `--confirm`, and wrong confirmation values across SkyDiscover catalog remove, validation remove, source remove, inspection checkout remove, experiment worktree remove, annotation remove, experiment remove, project remove, artifact remove, log remove, and run remove.
- Kept each assertion immediately before the successful actual remove path, after the target is already in a dependency-ready state, so the tests verify the confirmation guard instead of unrelated lifecycle blockers.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archive Idempotence Audit Coverage

Implemented:

- Tightened archive/unarchive idempotence so repeated archive operations reuse the stored archive timestamp instead of rendering a fresh timestamp, while repeated unarchive operations render `none` when no state transition occurs.
- Cleared `archived_at` on validation, run, artifact, and log unarchive transitions so a later real archive records a new archive timestamp, while no-op archives preserve the existing timestamp.
- Added smoke coverage proving repeated archive/unarchive operations do not create duplicate audit rows across project, validation, source, experiment, run, artifact, log, and annotation lifecycle surfaces.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Actual Remove Not-Archived Error Coverage

Implemented:

- Added a shared smoke-test assertion for actual destructive remove attempts against unarchived targets.
- Extended coverage across validation, source, log, artifact, annotation, experiment, project, and run removal paths to verify they fail with `RESOURCE_BUSY`, render the stable `target_not_archived` blocker, and do not create a `remove` audit row.
- Kept this separate from dry-run coverage so the V1 contract is now checked for both non-mutating planning output and the guarded destructive path.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Remove Dry-Run No-Write Coverage

Implemented:

- Added a shared smoke-test assertion proving remove dry-runs do not create `remove` audit rows and do not delete the authoritative database row for the target.
- Extended dry-run preservation coverage across validation, source, log, artifact, annotation, experiment, project, and run hard-remove paths, including both blocked and dependency-ready dry-run cases where available.
- Added explicit worktree and inspection checkout dry-run preservation checks for filesystem presence plus active token/path/experiment state, because those commands stage filesystem and credential mutations during actual removal.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Actual Cascade Blocker No-Mutation Coverage

Implemented:

- Added a shared smoke-test assertion for actual destructive remove attempts that are stopped by lifecycle dependency blockers.
- Extended validation, source, and run removal coverage so both no-cascade `dependent_records_require_cascade` blockers and active-child `dependent_records_not_archived` cascade blockers return `RESOURCE_BUSY` without creating `remove` audit rows.
- Verified the guarded paths preserve target rows, dependent rows, filesystem artifacts/logs, and the source Git ref where applicable before the successful archived-dependency removal path runs.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Active Lock Archive And Remove Guard Coverage

Implemented:

- Added smoke helpers for inserting and clearing deterministic active lifecycle locks.
- Extended experiment lifecycle coverage so `exp archive` and actual `exp remove --cascade` fail with `RESOURCE_BUSY` while an active experiment lock exists, without writing archive/remove audit rows or deleting filesystem/Git state.
- Extended project lifecycle coverage so `project archive` and actual `project remove --cascade` fail with `RESOURCE_BUSY` while an active project lock exists, without writing archive/remove audit rows or deleting project/control/worktree/inspection paths.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Worktree Restore Guard Coverage

Implemented:

- Added smoke coverage proving `exp worktree restore` fails with `RESOURCE_BUSY` while the experiment still has an active worktree, before creating the requested restore path or writing restore audit rows.
- Added non-empty destination coverage proving restore fails with `OUTPUT_EXISTS` before writing `.alab` metadata, creating a token/path registry row, changing `worktree_state`, or writing restore audit rows.
- Kept the existing successful restore path after these failure checks, so the test still verifies marker/token creation and active worktree state once the destination is valid.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Worktree Restore Nesting Guard Coverage

Implemented:

- Added direct restore path nesting coverage for `exp worktree restore` targets located inside an existing experiment context.
- Verified the nested restore attempt fails with `CONTEXT_CONFLICT`, does not create the requested nested path, and does not write a restore audit row.
- Kept this alongside active-worktree and non-empty-destination restore guards so restore preflight now exercises context nesting, active state, and destination occupancy separately.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Inspection Checkout Path Guard Coverage

Implemented:

- Added inspection checkout creation preflight coverage for targets nested inside an existing experiment context.
- Added non-empty inspection checkout destination coverage proving checkout fails before writing `.alab` metadata, creating an inspection token/path registry row, or writing an `inspection_checkout` add audit row.
- Verified the successful checkout path still creates exactly one add audit row after those guarded failures.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Dedupe Archived-Source Coverage

Implemented:

- Added focused smoke coverage for active source content dedupe, proving a second import with the same canonical tree hash returns the existing source id/ref and does not write a second source add audit row.
- Verified deduped imports append sanitized `origin_metadata_json.origins` entries without storing local source paths, while preserving the original `primary_origin`.
- Covered explicit-name mismatch behavior by asserting `SOURCE_DEDUPED_NAME_IGNORED` renders and is stored on the appended origin entry.
- Added standalone root/admin source name slug conflict coverage, proving a different tree with the same normalized name fails with `NAME_CONFLICT` before writing source rows or add audit rows.
- Verified archived sources are ignored for dedupe lookup: after archiving the old source, importing the same content creates a new active source with the same tree hash and a distinct id/ref.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Selector Option Scope Guard

Implemented:

- Added shared source option scope validation so `--git-ref` is accepted only with `--source-git` across project init, standalone source import, and experiment inline source creation.
- Added shared `--source-subdir` scope validation so it is accepted only with `--source-path` or `--source-git`, while preserving the specific `--source-subdir conflicts with --source-empty` error.
- Added smoke coverage proving invalid standalone source import and experiment creation option combinations fail with `SOURCE_INVALID` before writing source/experiment rows, creating experiment worktrees, or writing add audit rows.
- Rechecked valid public inline local/Git source import and active-source dedupe coverage after the shared preflight change.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_rejects_runtime_flags tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Public Experiment Name Conflict Coverage

Implemented:

- Extended public no-key experiment creation coverage to prove normalized experiment name slug conflicts fail with `NAME_CONFLICT`.
- Verified the duplicate public create attempt does not create the requested worktree path, does not insert an experiment row, and does not write an experiment add audit row.
- Kept the existing public `--from-exp` latest-commit inheritance path in the same test, so the duplicate-name guard is checked without weakening the successful inheritance coverage.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Source Explicit Experiment Creation

Implemented:

- Updated `exp create --source-ref` to resolve retained source rows when the caller explicitly names a source ref, instead of requiring the source to be active in all cases.
- Preserved the active-only requirement for implicit default-source experiment creation.
- Enforced the V1 rule that creating a new experiment from an archived source requires root/admin credentials; public no-key creation is rejected before writing experiment rows, audit rows, or worktree files.
- Added smoke coverage proving root/admin can create an experiment from an archived source ref, the new worktree is populated from the archived source commit, and the source remains archived.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_admin_exp_create_can_bind_archived_source_ref -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived From-Experiment Inheritance Coverage

Implemented:

- Extended public `--from-exp` coverage to archive the source experiment after proving ordinary public latest-commit inheritance works.
- Verified public no-key inheritance from an archived source experiment fails with `SCOPE_VIOLATION` before creating a worktree, inserting an experiment row, or writing an experiment add audit row.
- Verified root/admin can still create a new experiment from the archived source experiment, with the expected latest baseline commit, `from_exp` metadata, and no new source row.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 From-Commit SHA Selector Guard

Implemented:

- Tightened experiment commit selector resolution so custom selectors must be SHA-like values; arbitrary Git refs such as `HEAD` are no longer accepted as V1 `--from-commit` or checkout commit selectors.
- Preserved the named selectors `latest`, `final`, and `best`, and kept reachability checks for SHA selectors against the source experiment branch.
- Extended public `--from-exp` coverage to prove a non-SHA `--from-commit HEAD` fails with `CONFIG_INVALID` before writing experiment rows, audit rows, or worktree files.
- Added public full-SHA `--from-commit` success coverage proving the new experiment stores the requested selector and resolved commit without creating a new source row.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Public From-Commit Final And Best Coverage

Implemented:

- Extended public `--from-exp` coverage to close the source experiment with `submit`, then create children using `--from-commit final` and `--from-commit best`.
- Added no-write failure coverage for `--from-commit best` before any qualifying run exists and for `--from-commit final` before the source experiment has a final commit.
- Verified `final` resolves to the stored final commit on a closed experiment, preserves `from_exp` metadata, and does not create a new source row.
- Verified `best` resolves through the active reward policy's best-run selection, stores `from_commit: best` plus the resolved commit, and preserves the same source lineage.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Inspection Checkout Commit Selector Guard

Implemented:

- Extended inspection checkout preflight coverage so `exp checkout --commit HEAD` is rejected as a non-SHA custom selector.
- Verified the invalid checkout selector fails with `CONFIG_INVALID` before creating the checkout directory, inspection token/path rows, or an `inspection_checkout` add audit row.
- Kept the successful `--commit latest` checkout in the same flow to verify the valid selector still creates exactly one inspection checkout after the guarded failures.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Annotation Commitish Alias Resolution

Implemented:

- Split annotation target commitish handling from strict experiment creation/checkout selector handling so annotation targets can still use the documented `HEAD`/`head` aliases.
- Added smoke coverage for `path:<exp_id>@HEAD:<repo_path>`, `lines:<exp_id>@best:<repo_path>:<range>`, and `path:<exp_id>@final:<repo_path>`, proving annotation aliases resolve at creation time to concrete commits.
- Verified stored annotation `target_id`, `target_json.commit`, and `resolved_commit` all contain the concrete commit SHA instead of the moving alias.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project-Context Annotation Shorthand Rejection Coverage

Implemented:

- Added smoke coverage proving `path:<repo_path>` shorthand is rejected from project/admin context because it does not identify exactly one experiment.
- Verified the rejected project-context annotation target writes no `annotations` or `annotation_revisions` rows before the test returns to experiment context and successfully creates shorthand path annotations.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Regenerated Token Private Annotation Coverage

Implemented:

- Extended regenerated worktree token coverage to explicitly show and edit an experiment-private annotation created by the previous token for the same experiment.
- Verified private annotation ownership remains experiment-bound rather than raw-token-bound by expecting the regenerated token edit to create revision 3.
- Updated annotation remove dry-run/actual checks and audit metadata assertions to preserve the new revision count through hard removal.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Invalid Project Active-Valid Preservation

Implemented:

- Preserved `projects.active_valid_config_version` and `projects.active_validation_id` when a later runtime-affecting config is skipped, fails baseline validation, fails manual `project validate`, or is interrupted as stale.
- Kept invalid projects blocked for experiment creation through the capability resolver while allowing read-only observe/best flows to use the previous active-valid reward policy identity.
- Added smoke coverage proving `project config show --version active-valid` still works after `--skip-baseline-test`, failed manual validation preserves the previous active validation, and `observe experiments best` still ranks with the active-valid identity after a later failed runtime config attempt.
- Updated stale-running validation coverage to assert stale cleanup marks the project invalid without discarding the already-proven active-valid config reference.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Experiment Observe Visibility Coverage

Implemented:

- Extended experiment ranking/search smoke coverage with an archived experiment that has a better comparable reward than the active best experiment.
- Verified archived experiments are hidden by default from `exp list`, `exp search`, and `observe experiments best`.
- Verified `--include-archived` explicitly includes archived experiments in list/search output and allows `best` to rank the archived comparable run when requested.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Observe Authorization Coverage

Implemented:

- Extended the Harbor smoke flow to exercise hidden verifier logs through the public observe/log CLI surface after a successful adapter run.
- Verified worktree tokens cannot show hidden logs and cannot bypass that restriction with `logs export --include-hidden`; the rejected export writes no output file.
- Verified root/admin callers also need explicit `--include-hidden` to show a hidden log, while `logs list` hides hidden streams by default and includes them only when requested.
- Verified root/admin hidden-log export writes the exact stored bytes, which are already secret-redacted before storage.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment Search Corpus Boundary Coverage

Implemented:

- Extended experiment search/ranking smoke coverage so runner stdout, runner stderr, and captured artifact bytes contain unique search needles that must not appear in `exp search` results.
- Added current-vs-historical annotation coverage: the current annotation body remains searchable, while the body from a superseded annotation revision is excluded from the search corpus.
- Kept the existing private-annotation search visibility checks in the same flow so search now covers allowed text, private visibility, and excluded storage surfaces together.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Regenerated Token Lifecycle Permission Coverage

Implemented:

- Extended the regenerated worktree token smoke flow so the restored/regenerated token archives and unarchives its own experiment's run, captured artifact, and visible stdout log.
- Added a run artifact to the collaboration fixture so artifact lifecycle permission is covered alongside run and log lifecycle permissions.
- Verified each regenerated-token archive/unarchive operation renders the expected status transition and writes exactly one audit event for the corresponding object type.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Lifecycle Permission Coverage

Implemented:

- Extended the Harbor hidden-log smoke flow to cover lifecycle permissions after hidden-log show/list/export checks.
- Verified a worktree token cannot archive a hidden log and that the rejected operation leaves both the log archive status and audit log unchanged.
- Verified root/admin can archive and unarchive the hidden log by id, with expected status transitions and one audit event per transition.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Remove Coverage

Implemented:

- Extended the Harbor hidden-log lifecycle smoke flow through hard remove.
- Verified experiment context cannot remove a hidden log, and the rejected command leaves the log row, file, and remove audit state untouched.
- Verified root/admin hidden-log remove dry-run reports `target_not_archived`, planned trash staging, and no filesystem mutation while the log is still active.
- Verified root/admin can remove an archived hidden log, deleting the file-backed bytes through the trash flow and deleting the SQLite row with one remove audit event.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Annotation List Created-By And Archive Coverage

Implemented:

- Extended annotation list smoke coverage for `--created-by` matching the creator experiment id and for a nonmatching creator returning no rows.
- Verified archived annotations are hidden from list output by default and reappear with `--include-archived`.
- Kept the checks inside the regenerated-token/private-annotation flow so ownership, current-revision query filtering, and archive visibility are exercised together.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run Failure Reason Observe Coverage

Implemented:

- Normalized saved runner failure reasons for run and validation records so nonzero local runner exits store the same `runner exited with code N` reason that CLI result-failure output renders.
- Fixed CLI exit-code inference so read-only observe/list/show blocks that merely display failed saved runs do not exit `1` unless the block is an actual saved result-failure response with `error code` fields.
- Added smoke coverage proving `runs list --failure-reason-query` can find a failed saved run by its normalized reason and returns an empty successful list for a nonmatching reason.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run List Filter Contract Coverage

Implemented:

- Extended run observe smoke coverage for `--config-version`, `--commit`, `--reward-min`, `--reward-max`, `--started-after`, `--started-before`, `--ended-after`, and `--ended-before`.
- Verified the combined exact-bound filters still return the expected run with stable run list field ordering.
- Added empty-result checks for a reward lower bound and a future started-time filter that exclude the saved run without command failure.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Artifact And Log List Filter Coverage

Implemented:

- Extended log list smoke coverage for `--created-after` and `--created-before` around a saved stdout log, plus an empty-result future timestamp check.
- Extended artifact list smoke coverage for `--content-hash`, `--size-max`, `--created-after`, and `--created-before` in combination with the existing exp/run/root/status/path/size-min filters.
- Added empty-result checks for a nonmatching artifact content hash and future artifact timestamp.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Validation Artifact And Log Filter Coverage

Implemented:

- Added observe coverage for `artifacts list --validation <validation_id>` against baseline validation artifact records.
- Added observe coverage for `logs list --validation <validation_id> --stream stdout` against baseline validation log records.
- Verified incomplete validation selectors are rejected before listing validation artifacts.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Artifact And Log List Coverage

Implemented:

- Added log list coverage proving archived visible logs are hidden by default and return with `--include-archived`.
- Added artifact list coverage proving archived artifacts are hidden by default and return with `--include-archived`.
- Kept the checks next to archived show/export assertions so list, show, and export archived semantics stay covered together.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Run List Coverage

Implemented:

- Added run list coverage proving archived runs are hidden from list output by default.
- Verified `runs list --include-archived` returns the archived run while preserving the saved run status.
- Verified an archived run remains showable by id for an authorized admin before hard remove.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment List And Search Filter Coverage

Implemented:

- Extended experiment list smoke coverage for `--source-id`, `--name-query`, `--config-version`, `--created-after`, `--created-before`, `--updated-after`, and `--updated-before`.
- Verified incomplete `--source-id` selectors are rejected before experiment listing.
- Added experiment search coverage for `--reward-max`, complementing the existing reward minimum filtering.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment Best Filter Coverage

Implemented:

- Extended experiment best smoke coverage for explicit `--config-version` selection.
- Added `exp best --reward-max` coverage proving lower-ranked qualifying runs remain selectable after filtering out higher rewards.
- Added empty-result coverage for `exp best --reward-min` when no qualifying run satisfies the lower bound.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe Pagination Coverage

Implemented:

- Added `--limit` plus `--offset` smoke coverage for experiment list pagination with reward sorting.
- Added search pagination coverage using the same stable reward ordering.
- Added best pagination coverage and invalid pagination boundary checks for `--limit 0`, `--limit 501`, and negative `--offset`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe List Pagination Coverage

Implemented:

- Added focused smoke coverage for observe list pagination across runs, artifacts, logs, and annotations.
- Verified pagination is applied after deterministic sorting for `runs list`, `artifacts list`, `logs list`, and `annotations list`.
- Verified the shared observe pagination parser rejects non-integer `--limit` values with `CONFIG_INVALID`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_observe_list_pagination_contracts -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Backup Prune Selector Coverage

Implemented:

- Extended root/auth smoke coverage for `backup prune` selector validation.
- Verified `backup prune --older-than <days>` prunes only stale backup files while preserving fresh backups.
- Verified missing selectors, conflicting `--keep` plus `--older-than`, non-integer `--keep`, and negative `--older-than` fail with `CONFIG_INVALID` without pruning backups.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Cache Prune Selector Coverage

Implemented:

- Extended cache prune smoke coverage for the V1 selector matrix.
- Verified `cache prune --trash --older-than <days>` removes only stale active trash cache entries and preserves fresh trash cache entries.
- Verified `--trash-all` removes the remaining fresh trash entry after the age-filtered prune.
- Verified missing selectors, `--all` conflicts, trash selector conflicts, missing `--older-than`, unsupported `--older-than` placement, and non-integer `--older-than` fail with `CONFIG_INVALID` without deleting trash paths.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project List Archived Visibility Fix

Implemented:

- Fixed `project list` so archived projects are hidden by default and returned only with `--include-archived`.
- Added lifecycle smoke coverage proving a project appears in root `project list` before archive, disappears from default list after archive, and remains visible with `--include-archived`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Archive Visibility Coverage

Implemented:

- Added smoke coverage proving `source archive` rejects the active default source with `RESOURCE_BUSY` and writes no archive audit event.
- Added source list visibility coverage proving archived non-default sources are hidden by default and returned with `--include-archived`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe Lifecycle Own-Experiment Permission Fix

Implemented:

- Tightened run/artifact/log archive and unarchive handlers so token callers may mutate lifecycle state only for records from their own experiment.
- Preserved broader same-project observe read visibility while blocking cross-experiment lifecycle mutation with non-disclosing `SCOPE_VIOLATION`.
- Fixed the ranking/search smoke fixture so its declared `run:` artifact is actually written under `ALAB_RUN_DIR` and captured as an artifact.
- Added coverage proving a token can show a visible same-project experiment but cannot archive or unarchive that other experiment's run, artifact, or visible log.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Import Limit Atomicity Coverage

Implemented:

- Added a source-ref inspection helper for smoke tests so source import failures can assert against canonical Git refs, not only SQLite rows.
- Added standalone `source import` limit-failure coverage for max-files, max-file-bytes, and max-total-bytes failures, proving `SOURCE_LIMIT_EXCEEDED` leaves no new source row, no failed source name, no new `alab/source/*` Git ref, and no new source add audit event.
- Added public inline `exp create --source-path` coverage proving no-key callers cannot raise any source import limit above `[public_source_import]` policy, and that both policy-ceiling and policy-exceeded failures leave no source row, experiment row, Git source ref, source add audit, or worktree path.
- Added public inline source-name conflict coverage proving derived source names receive a deterministic source-id suffix instead of failing with `NAME_CONFLICT`, while the normalized slug remains unique.
- Added disabled public source-import policy coverage proving public no-key `exp create` with the default source still works, public no-key inline source import requires admin/root credentials without partial writes, and admin inline source import remains allowed.
- Added public inline `--source-empty` coverage proving explicit empty-source creation renders no empty-filter warning, stores empty origin metadata without warnings, creates an empty source tree, and records inline-source experiment provenance.
- Added public inline source dedupe coverage proving a no-key inline import with the same tree as an active source reuses the existing source id/ref, appends origin metadata without warnings, creates no new Git source ref, and still records inline-source experiment provenance.
- Added public inline local `--source-subdir` coverage proving only the selected subdirectory is imported, parent/outside files stay out of the worktree and source ref, and origin metadata stores only structured `source_subdir` without raw source paths.
- Git source origin metadata now records the resolved upstream commit, and public inline Git coverage proves both explicit `--git-ref` and omitted-`--git-ref` remote-HEAD imports store structured `git_ref`, `resolved_commit`, and `source_subdir` metadata without raw Git URLs while preserving credential-helper warnings.
- Added public inline Git `--source-subdir` coverage proving only the selected Git subdirectory is imported.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_standalone_source_import_limit_failure_is_atomic -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Active Validation Lifecycle Blocker Coverage

Implemented:

- Extended validation lifecycle smoke coverage so the validation currently proving `projects.active_valid_config_version` cannot be archived.
- Added dry-run and forced `project validation remove --cascade` coverage proving the active validation renders stable blockers, writes no remove audit, remains the project `active_validation_id`, and stays unarchived; the forced path is blocked with `RESOURCE_BUSY active_validation`.
- Kept the existing non-active validation archive/unarchive/remove cascade coverage in the same fixture to lock the contrast between removable historical validations and the active validation proof.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Unarchive Permission Coverage

Implemented:

- Extended Harbor hidden-log lifecycle coverage so a worktree token cannot unarchive a hidden log after root/admin archives it.
- Verified the token path returns non-disclosing `SCOPE_VIOLATION`, writes no unarchive audit, and leaves the hidden log archived until root/admin unarchives it.
- Kept this alongside existing hidden-log show/export/list/archive/remove checks to cover the full hidden-log lifecycle permission surface.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Public History Preflight Coverage

Implemented:

- Extended public `exp create --from-exp` smoke coverage to prove public no-key history observation remains rejected even when public inheritance is allowed.
- Verified public no-key `observe experiments show` and `runs list` fail at capability preflight with `COMMAND_UNAVAILABLE`, not handler-level visibility disclosure.
- Verified public no-key `exp checkout` is rejected before creating an inspection worktree or audit row, keeping checkout/history access token-bound as specified.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Removed Experiment Archive Flag Coverage

Implemented:

- Updated `cmd_exp_archive` to reject the removed V1 worktree-removal flags `--remove-worktree` and `--force-remove-worktree` with `CONFIG_INVALID`.
- Extended experiment removal smoke coverage to prove those flags do not archive the experiment, write no archive audit row, and direct callers to the explicit `exp worktree remove` command.
- Kept the existing active-lock and idempotent archive/unarchive checks in the same lifecycle fixture so removed-flag rejection stays separate from real archive state transitions.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Runtime Flag Rejection

Implemented:

- Added a `project init` runtime-flag guard so V1 init rejects runner, reward, artifact, log, env, secret, Docker, Harbor, and SkyDiscover override-style flags with `CONFIG_INVALID` instead of silently ignoring them.
- Kept source bootstrap flags, source limits, display overrides, and `--skip-baseline-test` as the only accepted init-time options beyond mode and `--config`.
- Added smoke coverage proving rejected runtime flags leave no project rows, source rows, or generated admin credentials behind.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_rejects_runtime_flags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Source Ref Mismatch Cleanup

Implemented:

- Fixed `project init` staging cleanup so a config-provided `source.default_source_ref` mismatch removes prepared final project and control paths when no visible project rows have been written.
- Tracked whether the initial project/source/config/admin transaction has committed, preserving retained-project baseline semantics after rows become authoritative while still cleaning pre-commit staging failures.
- Added smoke coverage proving a mismatched source ref returns `CONFIG_INVALID`, writes no project/source/config/admin rows, and leaves `projects/`, `project-workspaces/`, and the init staging directory empty.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_rejects_runtime_flags tests/test_smoke.py::test_project_init_source_ref_mismatch_cleans_staged_paths -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit Stdin Option Rejection

Implemented:

- Added explicit `submit` preflight rejection for unsupported V1 stdin options `--summary-stdin` and `--feedback-stdin`.
- Kept submit input handling limited to direct text or file inputs, even when callers also provide otherwise-valid `--summary` and `--feedback` values.
- Extended submit failure/input smoke coverage to prove stdin options return `CONFIG_INVALID` and do not create run records.
- Added matching `annotate` coverage and handler rejection for unsupported `--body-stdin`, proving add writes no annotation/revision rows and edit does not advance `current_revision`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Gitlink Source Rejection Next Action

Implemented:

- Added the documented next action to shared Git submodule/gitlink rejection so callers are told to vendor or expand submodule contents before importing.
- Extended source fidelity smoke coverage with a real Git index gitlink fixture.
- Verified `source import` rejects the gitlink with `SOURCE_INVALID`, writes no source row, creates no source add audit row, and leaves the project's Git source refs unchanged.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Source Origin Requirement

Implemented:

- Tightened `project init local|git|empty` so each mode requires its explicit source origin flag (`--source-path`, `--source-git`, `--source-empty`) and missing origins return `SOURCE_INVALID`.
- Kept source-origin conflicts on the existing `SOURCE_INVALID` path while avoiding generic required-option failures for mode-specific missing origins.
- Added smoke coverage proving missing mode-specific source origins write no project/source/config/admin rows and leave ALab project/control/staging paths empty.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Import Existing Selector Rejection

Implemented:

- Tightened `source import` so existing-source and experiment-inheritance selectors (`--source-ref`, `--from-exp`, `--from-commit`) are rejected with `SOURCE_INVALID` instead of being silently ignored beside a real import origin.
- Kept standalone `source import` limited to the documented creation origins: `--source-path`, `--source-git`, or `--source-empty`.
- Extended source selector smoke coverage proving rejected existing selectors do not write source rows, experiment rows, or source/experiment add audit rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate Source Origin Rejection

Implemented:

- Tightened shared source-origin parsing so repeated origin options count as multiple origins instead of being collapsed by first-value lookup.
- `project init`, standalone `source import`, and inline `exp create` now reject duplicate source selectors such as repeated `--source-path` or repeated `--source-ref` with `SOURCE_INVALID`.
- Extended smoke coverage proving duplicate origin rejection leaves project/source/config/admin rows untouched for init, and leaves source/experiment rows plus add audit rows untouched for source import and experiment creation.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate From-Experiment Origin Rejection

Implemented:

- Tightened `exp create` so repeated `--from-exp` values are treated as duplicate source origins and rejected with `SOURCE_INVALID`.
- Preserved the public `--from-exp` inheritance path while preventing first-value lookup from silently discarding later origin selectors.
- Extended from-experiment smoke coverage proving duplicate `--from-exp` creates no worktree, writes no experiment rows, and writes no experiment add audit row.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate From-Commit Selector Rejection

Implemented:

- Added shared option occurrence counting for source/experiment selector validation.
- Tightened `exp create --from-exp` so repeated `--from-commit` values fail with `CONFIG_INVALID` instead of silently using the first selector.
- Extended from-experiment smoke coverage proving duplicate `--from-commit` creates no worktree, writes no experiment rows, and writes no experiment add audit row.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Secret Duplicate Input Rejection

Implemented:

- Tightened `project secret set` input validation so repeated `--value-file` or repeated `--value-stdin` fails the documented exactly-one input contract with `CONFIG_INVALID`.
- Reused shared option occurrence counting so the secret path no longer relies on first-value lookup for mutually exclusive input options.
- Extended secret input smoke coverage proving duplicate input options write no `secret_values`, create no project config version, and write no audit rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit And Annotation Duplicate Input Rejection

Implemented:

- Reused shared option occurrence counting for text input pairs that have an exactly-one CLI contract.
- Tightened `submit` so repeated `--summary`, repeated `--summary-file`, repeated `--feedback`, or repeated `--feedback-file` fail with `CONFIG_INVALID` before file reads or runner execution.
- Tightened `annotate add|edit` so repeated `--body`, repeated `--body-file`, or mixed body inputs fail with `CONFIG_INVALID` before body file reads or annotation revision writes.
- Extended smoke coverage proving duplicate submit inputs create no run rows, duplicate annotation add inputs create no annotation/revision rows, and duplicate annotation edit inputs do not advance `current_revision`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Checkout Remove Duplicate Selector Rejection

Implemented:

- Tightened `exp checkout remove` so repeated `--token-id`, repeated `--path`, or mixed selector inputs fail the documented exactly-one selector contract with `CONFIG_INVALID`.
- Moved checkout-remove selector validation to shared option occurrence counting before inspection lookup or filesystem trash staging.
- Extended inspection checkout smoke coverage proving duplicate remove selectors leave the checkout path present, keep the inspection path/token active, and write no remove audit rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment Token Duplicate Selector Rejection

Implemented:

- Tightened `exp token list|revoke|regenerate` so repeated selector options (`--token-id`, `--mode`, `--all`) fail with `CONFIG_INVALID` instead of silently using the first occurrence.
- Applied the guard before token selection/mutation so revoke and regenerate cannot accidentally target a narrower or broader token set than requested.
- Extended token lifecycle smoke coverage proving duplicate selectors leave token rows, active token counts, restored token status, and audit rows unchanged.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Prune And Secret GC Duplicate Selector Rejection

Implemented:

- Tightened `backup prune` so repeated `--keep` or repeated `--older-than` fail the exactly-one selector contract with `CONFIG_INVALID` before deleting backup files.
- Tightened `project secret gc` so repeated `--dry-run` or repeated `--apply` fail with `CONFIG_INVALID` before reading or deleting unreferenced secret rows.
- Extended smoke coverage proving duplicate prune selectors keep backup files present, and duplicate secret GC selectors keep orphan secret rows and audit counts unchanged.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Cache Prune Duplicate Selector Rejection

Implemented:

- Tightened `cache prune` so repeated selectors (`--all`, `--docker-images`, `--skydiscover-envs`, `--trash`, `--trash-all`) and repeated `--older-than` fail with `CONFIG_INVALID`.
- Kept duplicate selector rejection ahead of cache row selection and path deletion, including trash cache cleanup.
- Extended cache prune smoke coverage proving duplicate selectors keep active trash cache rows and staged trash paths intact.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Catalog Duplicate Selector Rejection

Implemented:

- Tightened `catalog skydiscover add|update` so repeated `--origin-url`, `--ref`, or `--commit` values fail with `CONFIG_INVALID`.
- Kept duplicate selector rejection before clone/fetch/checkout and before catalog row or audit writes.
- Extended catalog lifecycle smoke coverage proving duplicate add selectors create no local catalog contents, catalog rows, or catalog audit rows, and duplicate update selectors keep the pinned commit and update audit count unchanged.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hard Remove Duplicate Confirmation Rejection

Implemented:

- Added shared `require_force_confirm` handling for actual hard-remove confirmation checks.
- Tightened catalog/project/source/experiment/worktree/checkout/validation/run/artifact/log/annotation remove paths so duplicate `--force` or duplicate `--confirm` values fail with `CONFIG_INVALID` instead of being collapsed by flag/first-value parsing.
- Extended the shared confirm guard smoke helper to cover duplicate force/confirm variants across the existing destructive lifecycle tests.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Config Duplicate Option Rejection

Implemented:

- Added shared `require_options_at_most_once` handling for single-value or single-use command options.
- Tightened `project init` for duplicate `--config`, config text overrides, source subdir/ref selectors, and `--skip-baseline-test` before source staging or project rows are written.
- Tightened `project config show|export|import` and project config mutation surfaces so duplicate `--version`, `--out`, `--config`, `--overwrite`, `--dry-run`, or `--skip-baseline-test` fail with `CONFIG_INVALID` instead of silently using the first option.
- Extended smoke coverage proving duplicate init/config options leave project/config/audit rows and export files unchanged.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe Query Duplicate Option Rejection

Implemented:

- Extended duplicate option rejection to `run`, `submit`, pagination, numeric filters, boolean filters, time filters, complete-id option filters, and sort parsing.
- Tightened observe run/artifact/log list and export surfaces so duplicate filter, sort, pagination, `--out`, `--overwrite`, and include flags fail with `CONFIG_INVALID` instead of silently using the first option.
- Extended smoke coverage proving duplicate run/submit options do not create runs, duplicate observe filters render stable errors, and duplicate export destinations create no files.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_observe_list_pagination_contracts tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Collaboration Duplicate Option Rejection

Implemented:

- Extended duplicate option rejection to shared project-id parsing, source import limits, source subdir/ref helpers, experiment visibility options, context path commands, experiment checkout/restore paths, annotation target/list/show options, and audit filters.
- Tightened source import, experiment creation, annotation mutation/list/show, context show/repair, checkout creation, and audit list/show so repeated single-value options fail with `CONFIG_INVALID` instead of being collapsed by first-value parsing.
- Extended smoke coverage proving duplicate collaboration/source/audit/context options leave source/experiment/annotation/audit rows and checkout/export paths unchanged.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Key And Lifecycle Duplicate Option Rejection

Implemented:

- Extended duplicate option rejection to key management, project list/show, and the shared lifecycle reason parser.
- Tightened key create/list/revoke, project list/show, and project/source/worktree remove reason parsing so repeated single-value options fail with `CONFIG_INVALID` before writes.
- Extended smoke coverage proving duplicate key/project/lifecycle options render stable errors and leave credential, audit, and lifecycle target rows unchanged where relevant.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Lifecycle Remove Duplicate Flag Rejection

Implemented:

- Extended destructive lifecycle smoke coverage for repeated `--dry-run` and `--cascade` options across project, source, validation, experiment, worktree, inspection checkout, run, artifact, log, and annotation remove flows.
- Confirmed those duplicate flags fail with `CONFIG_INVALID` before mutation and preserve rows, credentials, audit events, and filesystem paths on the exercised paths.
- Kept the lifecycle flag behavior aligned with the shared single-value option parser used by the rest of the CLI.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_observe_list_pagination_contracts tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Config Duplicate Option Rejection

Implemented:

- Extended shared duplicate option rejection to global `config reset --all` and `config validate --refresh-capabilities`.
- Tightened config repair and validation surfaces so repeated boolean options fail with `CONFIG_INVALID` before mutating config files or probing runtime capabilities.
- Extended smoke coverage for duplicate global config flags alongside the existing config reset/validate repair flow.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Option Duplicate Coverage

Implemented:

- Extended global option pre-scan smoke coverage for duplicate `--home`, `--output`, `--key`, and repeated `--key-stdin`.
- Verified duplicate global options render stable `CONFIG_INVALID` errors before command execution, while standalone `--` still stops global parsing.
- Kept this as test-only golden coverage because the implementation already enforced the contract.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Key Stdin Input Contract Coverage

Implemented:

- Extended global option pre-scan smoke coverage for invalid `--key-stdin` input values.
- Verified empty stdin, a lone newline, embedded newlines, NUL bytes, and extra trailing newlines fail with `CONFIG_INVALID` before command execution.
- Kept the standalone `--` stop-parsing behavior covered so command arguments that look like global options remain inert after the sentinel.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Option Value Contract Coverage

Implemented:

- Extended global option pre-scan smoke coverage for missing `--home`, `--output`, and `--key` values.
- Added explicit `--output json` rejection coverage, proving V1 remains limited to `text` and `rich` per the CLI contract.
- Verified these failures render stable `CONFIG_INVALID` error blocks before command handling.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Nested Help Duplicate Option Rejection

Implemented:

- Tightened nested command help parsing so repeated `--all` or `--explain` fails with `CONFIG_INVALID` instead of being silently collapsed.
- Kept top-level `help` and nested `--help` behavior aligned for duplicate help options.
- Extended smoke coverage for top-level duplicate `--all` and nested duplicate `--explain` while preserving the existing nested command help result schema.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Top-Level Help Option Error Coverage

Implemented:

- Extended top-level `alab --help` smoke coverage for invalid help options and duplicate `--explain`.
- Verified `alab --help` and `alab help` render the same stable `CONFIG_INVALID` error block shape for help option mistakes.
- Preserved existing nested command help schema checks while broadening the help-option golden matrix.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Nested Help Flag Duplicate Rejection

Implemented:

- Tightened nested command help parsing so repeated `--help` itself fails with `CONFIG_INVALID`.
- Kept duplicate handling consistent across `--help`, `--all`, and `--explain` in nested command help requests.
- Extended smoke coverage for `config show --help --help` while preserving valid nested help output for `config show --help`.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Trailing Global Option Coverage

Implemented:

- Extended smoke coverage for global options supplied after the command path, including `config show --home <path> --output rich`.
- Added a trailing invalid `--output json` case to prove post-command global parsing still enforces the V1 output enum.
- Preserved standalone `--` coverage showing global-looking arguments after the sentinel stay command-local.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate Option Helper Consolidation

Implemented:

- Consolidated catalog SkyDiscover add/update, cache prune, and experiment token selector duplicate-option checks onto `require_options_at_most_once`.
- Removed remaining local loops that duplicated the shared single-value option rejection behavior for those command families.
- Preserved existing error strings while reducing the chance of future CLI parser drift across catalog/cache/token surfaces.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Optional Authorization Ambient Key Hardening

Implemented:

- Tightened optional-authorized helper paths so `ALAB_KEY` no longer elevates public, experiment-token, or inspection-token command surfaces.
- Preserved ambient `ALAB_KEY` support for commands that genuinely require admin/root credentials through the central `require_actor` path.
- Added smoke coverage proving ambient admin keys do not unlock hidden-log reads, peer experiment tag mutation, admin-only private annotation targeting, mismatched inspection checkout removal, or context self-repair branch-check bypasses.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Fixed Positional Argument Count Hardening

Implemented:

- Added a shared fixed positional-count helper for commands whose CLI grammar requires an exact number of positional arguments.
- Tightened global `config set`, project config/env/secret mutators, and experiment tag add/remove so extra positional arguments fail with `CONFIG_INVALID` instead of being silently ignored.
- Added smoke coverage proving these extra-argument failures preserve config versions, secret rows, audit counts, global config values, and experiment tag rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Single Selector Argument Hardening

Implemented:

- Added a shared optional single-selector helper that preserves existing missing-selector `*_NOT_FOUND` behavior while rejecting extra positional selectors with `CONFIG_INVALID`.
- Tightened key revoke, config reset, validation lifecycle, source lifecycle/show, experiment show/lifecycle/worktree/token/checkout/tag-list, observe run/artifact/log show/export/lifecycle, annotation edit/status/remove/show, and audit show selector parsing.
- Added smoke coverage across representative command families proving extra selector arguments fail before revoking credentials, changing validation/source/tag/archive state, writing export files, editing annotations, or writing audit rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Mode Argument Hardening

Implemented:

- Tightened `project init` mode parsing to require exactly one positional mode instead of accepting the first mode and ignoring trailing positional arguments.
- Reused the shared fixed positional-count helper so missing, extra, and invalid modes keep the same `CONFIG_INVALID` user-facing contract.
- Added smoke coverage proving `project init local extra ...` fails before creating project, source, config-version, validation, admin credential, or add-audit rows.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Real SkyDiscover Python dependency-installation validation remains optional future environment hardening.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real SkyDiscover Python Dependency Install Coverage

Implemented:

- Added an opt-in `real_skydiscover_python` pytest marker and real-environment test gated by `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1`.
- The test builds a local pure-Python wheel at runtime, installs it through a real `uv` SkyDiscover evaluator environment, imports it from the evaluator, and verifies parsed reward/metrics.
- The same test verifies environment cache metadata transitions from `built` to `hit` without relying on network access.
- Updated README and test-spec documentation with the new opt-in command and skip behavior.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Maintenance No-Positional Argument Hardening

Implemented:

- Tightened `project secret gc` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Tightened `project locks clear-stale` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Added smoke coverage proving those failures preserve unreferenced secret rows, stale/live lock rows, and audit counts before any delete or clear operation runs.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Surface No-Positional Argument Hardening

Implemented:

- Tightened `project list`, `project show`, `project archive`, `project unarchive`, and `status` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved existing auth-first behavior for root/admin project surfaces while enforcing the documented option-only command grammar before project lifecycle writes.
- Added smoke coverage proving extra positional archive/unarchive attempts preserve project status and audit counts, and that read-only project/status commands reject the same grammar drift.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Auth And Global Config No-Positional Argument Hardening

Implemented:

- Tightened `auth init`, `auth root regenerate`, `config show`, and `config validate` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Ensured `auth init extra` fails before creating an ALab home, while `auth root regenerate extra` fails after root authentication but before revoking or creating root credentials.
- Added smoke coverage proving config read/validate no-positional failures render stable error blocks and do not continue into the normal command path.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Key Surface No-Positional Argument Hardening

Implemented:

- Tightened `key create` and `key list` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved credential checks before the grammar rejection on key-management surfaces, matching the existing auth-first behavior for protected commands.
- Added smoke coverage proving `key create extra ...` fails before adding admin credentials or add-audit rows, and that both root-scope and project-scope key list reject the same grammar drift.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Catalog Surface No-Positional Argument Hardening

Implemented:

- Tightened `catalog skydiscover add|update|show|remove` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Kept root credential checks and remove confirmation checks ahead of the new grammar rejection, while still failing before clone/fetch/update/delete/database lifecycle work.
- Added catalog lifecycle smoke coverage proving extra positional add/update/remove attempts preserve catalog rows, pinned commits, local catalog contents, and catalog audit counts.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Backup And Cache No-Positional Argument Hardening

Implemented:

- Tightened `backup prune` and `cache prune` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved existing selector/missing/conflict validation priority, while rejecting extra positional arguments before backup file deletion, trash path removal, cache row mutation, or audit writes.
- Added smoke coverage proving extra positional backup/cache prune attempts preserve backup files, active trash paths/rows, and audit counts.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project Validate No-Positional Argument Hardening

Implemented:

- Tightened `project validate` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Kept the existing admin-auth-first behavior for protected project maintenance, while rejecting extra positional arguments before validation row creation, baseline execution, project status mutation, or active validation pointer changes.
- Added smoke coverage proving `project validate extra --project <id>` preserves validation counts and project state before the real validation run.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project Config List/Import No-Positional Argument Hardening

Implemented:

- Tightened `project config show`, `project config export`, `project config import`, `project env list`, and `project secret list` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Kept protected project config surfaces auth-first, while rejecting extra positional arguments before config export writes, config import file reads, config version mutation, or audit writes.
- Extended smoke coverage for no-positional read/list commands plus export/import failure paths that preserve output files, config version counts, and audit counts.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Context Show/Repair No-Positional Argument Hardening

Implemented:

- Tightened `context show` and `context repair` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved duplicate `--path` and missing required `--path` validation priority, while rejecting extra positional arguments before context marker reads that can lead to repair writes.
- Added collaboration smoke coverage proving extra positional repair attempts preserve marker bytes and repair audit counts.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source List/Import No-Positional Argument Hardening

Implemented:

- Tightened `source list` and `source import` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved existing source-origin and unsupported-selector validation priority, while rejecting extra positional arguments before source-import temporary work directories, Git/source snapshot work, source row mutation, or source add audit writes.
- Added smoke coverage proving extra positional source import attempts preserve source row counts and source add audit counts, and that source list rejects the same grammar drift.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Experiment Create/Search No-Positional Argument Hardening

Implemented:

- Tightened `exp create`, `exp list`, `exp search`, and `exp best` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved existing source selector conflict and unsupported `exp best --sort` validation priority, while rejecting extra positional arguments before experiment row creation, worktree creation, token writes, path registry mutation, or observe queries.
- Added smoke coverage proving extra positional experiment create attempts preserve experiment counts and do not create the requested worktree, and that experiment list/search/best reject the same grammar drift.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Run And Submit No-Positional Argument Hardening

Implemented:

- Tightened top-level `run` and `submit` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Kept required message/body/ref validation priority, while rejecting extra positional arguments before runner execution, final-run reuse/rerun, summary/feedback file reads, submission writes, or experiment close mutation.
- Added workflow smoke coverage proving extra positional run attempts preserve run counts and extra positional submit attempts preserve submission counts while failing before missing summary-file reads.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project And Checkout Remove No-Positional Argument Hardening

Implemented:

- Tightened `project remove` and `exp checkout remove` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Preserved duplicate selector/option validation priority, while rejecting extra positional arguments before project whole-tree removal planning, trash staging, inspection checkout removal, token revocation, path registry mutation, or remove audit writes.
- Added smoke coverage proving extra positional remove attempts preserve project rows, project/control/worktree/inspection paths, inspection active path/token rows, and remove audit counts.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Observe List No-Positional Argument Hardening

Implemented:

- Tightened `runs list`, `artifacts list`, and `logs list` so extra positional arguments fail with `CONFIG_INVALID` instead of being ignored.
- Extended the shared positional parser to recognize additional observe filter options with values, including `--stream`, `--size-min`, `--size-max`, and `--truncated`, so valid filters remain accepted under the stricter grammar checks.
- Added observe smoke coverage proving extra positional list attempts render stable error blocks across runs, artifacts, and logs while preserving duplicate-option validation priority.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project-Context Invalid Status Hardening

Implemented:

- Tightened marker-only project-context `status` for invalid projects to use the same safe invalid-only output as explicit public `status --project <id>`.
- Preserved valid public status shape and experiment/inspection token status detail, while avoiding task/config rendering for no-key invalid project contexts.
- Added smoke coverage for invalid marker-only project context status output.

Known incomplete areas:

- The complete CLI golden matrix still has smaller long-tail gaps across uncommon source/config combinations and selected destructive failure variants.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Lifecycle Unsupported-Option Hardening

Implemented:

- Added a shared known-option guard for mutation-oriented lifecycle and credential surfaces so options from other commands cannot be silently skipped by the shared positional parser.
- Applied the guard to key revoke, project/source/experiment/validation lifecycle remove/archive/unarchive paths, worktree and inspection checkout lifecycle paths, observe record archive/unarchive/remove paths, and annotation archive/unarchive/remove paths.
- Added smoke coverage proving unsupported cross-command `--reason` inputs fail with `CONFIG_INVALID` before key revoke, source archive, log archive, experiment archive, or project archive side effects.

Known incomplete areas:

- Some non-mutating read-only surfaces still rely on command-specific duplicate/positional validation rather than a complete per-command unknown-option matrix.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Read Selector Unsupported-Option Hardening

Implemented:

- Extended the shared known-option guard to read-oriented selector/export surfaces, including source/experiment/run/artifact/log/annotation/audit show commands and artifact/log exports.
- Added the same guard to experiment token list selectors so token listing cannot silently ignore cross-command options.
- Added smoke coverage proving unsupported cross-command `--reason` inputs fail with `CONFIG_INVALID` before show/export reads complete or export files are written.

Known incomplete areas:

- Some broad list surfaces still rely on command-specific duplicate/positional validation rather than a complete per-command unknown-option matrix.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 List Surface Unsupported-Option Hardening

Implemented:

- Extended the shared known-option guard to broad list surfaces, including key, project, project env/secret, source, experiment query, experiment tag, observe run/artifact/log/annotation, and audit list commands.
- Preserved repeated `--tag` semantics and the existing `exp best --sort` unsupported-sort error while rejecting unrelated cross-command options earlier.
- Added smoke coverage proving unsupported cross-command `--reason` inputs fail with `CONFIG_INVALID` across representative root, project, source, experiment query, observe list, annotation list, and audit list surfaces.

Known incomplete areas:

- A full per-command unknown-option golden matrix is still not exhaustive across every configuration and adapter command variant.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Key List Root Flag Positional Hardening

Implemented:

- Added command-level positional value-option overrides so commands can distinguish shared option names that are values elsewhere but flags locally.
- Tightened `key list --root` so trailing positional arguments are no longer skipped because `--root` is a value filter on artifact list surfaces.
- Added smoke coverage for both `key list extra --root` and `key list --root extra` rejection paths.

Known incomplete areas:

- A full audit of every shared option name across all command contexts remains ongoing.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Run Submit Unsupported-Option Hardening

Implemented:

- Added known-option guards to the side-effectful `run` and `submit` workflow commands.
- Preserved submit's explicit unsupported `--summary-stdin` and `--feedback-stdin` messages while rejecting unrelated cross-command options before file reads, runner execution, or submission writes.
- Added smoke coverage proving unsupported `run --summary` does not create a run and unsupported `submit --path` does not create a submission.

Known incomplete areas:

- Remaining command surfaces still need the same per-command unknown-option audit, especially project config/env/secret mutation, init/import/create, context, cache, and catalog commands.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project Maintenance Unsupported-Option Hardening

Implemented:

- Added known-option guards to project config show/export/import/set, project env set/unset, project secret set/unset/gc, manual project validation, and stale-lock clearing.
- Preserved existing duplicate-option and positional validation messages while rejecting unrelated cross-command options before config file reads, config-version writes, stdin secret reads, validation runs, lock deletion, or lifecycle audit writes.
- Added smoke coverage proving unsupported `--reason` inputs do not create config versions, secret rows, validations, lock-clear audit rows, config export files, or import input files.

Known incomplete areas:

- Remaining command surfaces still need the same per-command unknown-option audit, especially init/import/create source surfaces, context, cache, and catalog commands.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Context Cache Catalog Unsupported-Option Hardening

Implemented:

- Added known-option guards to SkyDiscover catalog add/update/show/remove, backup prune, cache prune, context show, and context repair.
- Preserved existing selector, duplicate-option, confirm, and lifecycle reason validation while rejecting unrelated cross-command options before catalog Git operations, filesystem pruning, trash deletion, marker repair, path-registry mutation, or audit writes.
- Added smoke coverage proving unsupported options leave catalog rows/audit counts pinned, backup and trash files present, cache rows active, and context marker/audit state unchanged.

Known incomplete areas:

- Remaining command surfaces still need the same per-command unknown-option audit, especially project init, source import, public experiment create source selectors, annotation add/edit, and experiment token/checkout edge selectors.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source Create Unsupported-Option Hardening

Implemented:

- Added known-option guards to `project init`, `source import`, and `exp create`, including the documented source selector, inheritance, mutable policy, visibility, tag, and inline source limit options.
- Preserved existing runtime-flag rejection for `project init` and source-specific `SOURCE_INVALID` messages for invalid source import selectors such as `--source-ref`, `--from-exp`, and `--from-commit`.
- Added smoke coverage proving unsupported `--reason` inputs do not create project/source/config/validation/credential rows, source refs, experiment worktrees, source/experiment rows, or add-audit events.

Known incomplete areas:

- Remaining command surfaces still need the same per-command unknown-option audit, especially annotation add/edit and selected experiment token/checkout edge selectors.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_project_init_rejects_runtime_flags tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation Mutation Unsupported-Option Hardening

Implemented:

- Added known-option guards to `annotate add` and `annotate edit`, covering project targeting, target selectors, body inputs, author labels, and private visibility selectors.
- Preserved the explicit V1 `--body-stdin is not supported` message while rejecting unrelated cross-command options before body-file reads or annotation revision writes.
- Audited experiment token and checkout selector handlers in the current tree; those surfaces already use known-option guards from earlier increments.
- Added smoke coverage proving unsupported `--reason` inputs on annotation add/edit do not read missing body files and do not create annotation rows or revisions.

Known incomplete areas:

- The CLI unknown-option audit is now mostly down to scattered edge aliases and future adapter-specific command variants, but the complete golden matrix still needs broader enumerated coverage.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Core Command Unsupported-Option Hardening

Implemented:

- Added known-option guards to `auth init`, `auth root regenerate`, `key create`, global `config show|set|reset|validate`, `project show`, `status`, and experiment tag add/remove.
- Preserved existing positional and duplicate-option errors while rejecting unrelated cross-command options before home creation, root key rotation, admin key creation, config rewrites, status maintenance, project rendering, or tag mutation.
- Kept the documented standalone `--` command-local sentinel behavior: known-option guards stop scanning at `--`, so later tokens are not interpreted as command options.
- Added smoke coverage proving unsupported `--reason` inputs do not create homes, rotate root keys, create admin credentials, rewrite global config values, or mutate experiment tags.

Known incomplete areas:

- The strict CLI matrix still needs broader generated or table-driven coverage across all aliases, but the most common write and read surfaces now have explicit known-option guards.
- Broader live SkyDiscover catalog and networked dependency validation remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 CLI Known-Option Registry Contract

Implemented:

- Added a registry-level CLI contract test that walks every `registry.COMMANDS` handler and requires each non-help command to call `require_known_options` directly or delegate to one of the guarded shared observe/annotation helpers.
- Asserted that the shared observe archive/unarchive/remove helpers and annotation status helper keep their own known-option guard, so thin aliases such as `runs archive`, `observe logs remove`, and `annotate archive` remain covered without duplicating command-specific smoke flows.
- Added allowlist metadata checks requiring every `require_known_options` tuple to be literal, duplicate-free, and composed only of declared value options or explicitly classified flag options.
- Added registry alias and matcher contracts requiring unique command paths, an exact `COMMANDS_BY_PATH` mirror, stable credential surface names, longest-match behavior, and consistent object type/credential schema across shared-handler aliases.
- Added a registry object-type contract that now parses the canonical `docs/spec_cli.md` primary object-type table and fails future command additions when `registry.COMMANDS` metadata is missing, undocumented without a documented alias handler, or mapped to the wrong primary `object: <type>`.
- Added a paired CLI spec synchronization contract that parses the English and Chinese primary object-type tables with the same parser and fails if command coverage or object-type mappings drift between `docs/spec_cli.md` and `docs/spec_cli_cn.md`.
- Added a docs-derived stable error-code exit mapping contract that parses the English and Chinese CLI spec tables and requires both documents to match `ERROR_EXIT_CODES`, including prose-qualified `RUNNER_ERROR` exit `1` semantics.
- Added docs-derived success-field order contracts for low-side-effect global repair commands (`auth init`, `config show`, `config set`, and `config reset`), project initialization/read commands (`project init`, `project show`, and `project config show`), source read commands (`source list` and `source show`), credential key commands (`key create`, `key list --root`, `key list --project`, and `key revoke`), experiment/observe commands (`exp create`, `observe experiments list`, `observe experiments show`, `exp tag add`, `exp tag remove`, and `exp tag list`), local runner observe commands (`run`, `observe runs list`, and `observe runs show`), and run-scoped observable asset commands (`observe artifacts list`, `observe artifacts show`, `observe logs list`, and `observe logs show`), proving their rendered text field labels match the canonical English CLI spec order.
- Extended the `project init` docs-derived contract beyond the existing local-source path to cover `empty` and local `git` mode variants, proving both share the canonical init field order and raw admin-key one-time rendering rule without reprinting the root key.
- Extended the same `project init` mode-variant contract to Harbor and SkyDiscover adapter init paths using local fixture refs and skipped baseline validation, proving adapter-backed init also follows the canonical init field order and raw admin-key/root-key rendering rules.
- Added a docs-derived `auth root regenerate` success-field contract, including raw-key safety assertions that the revoked root key is not re-rendered, the replacement root key appears exactly once, and retained `audit show` metadata records sanitized regenerate context without raw key material.
- Added raw credential secret-rule coverage for `auth init`, `project init`, and `key create`, proving generated raw keys appear exactly once in their intended success object while caller credentials and prior admin keys stay hidden; key revoke now also has a docs-derived `audit show` metadata contract proving sanitized revoked-credential context is retained.
- Split global `config validate` success fields into explicit `config` and `capability` object schemas, synchronized the Chinese CLI spec, and added a docs-derived contract proving both rendered blocks follow their documented field order.
- Added docs-derived `project secret set`, `project secret list`, and `project secret unset` success-field contracts, including assertions that the raw secret value is not rendered while fingerprints and referenced status remain visible.
- Added a docs-derived `project secret gc` success-field contract and aligned its renderer with the CLI spec by emitting `dry run`, `deleted count`, repeated `secret value id`, and `audit id`, while no longer rendering candidate secret names.
- Extended the `project secret gc --apply` contract through `audit show`, proving retained sanitized metadata exposes deletion counts without leaking secret names or raw secret values.
- Split the CLI spec for `project env` success fields into `set|unset` mutation output and per-env `list` output, then added a docs-derived contract proving `project env set`, `project env list`, and `project env unset` follow those distinct schemas.
- Extended docs-derived success-field contracts to `project config export`, `project config import`, `project config set`, and `project validate`, including parser support for command headings with required options such as `--out` and for `project config set` inheriting the `project config import` success schema.
- Clarified the `project config export` secret rule to write retain markers and fingerprints without raw secret values, and added a docs-derived contract proving `project config show`/`export` keep raw secret values out of stdout and exported TOML while preserving secret names, fingerprints, and retain metadata.
- Aligned the CLI spec for `project locks clear-stale` with the audited lifecycle behavior by documenting `audit id`, then added a docs-derived contract covering both the no-stale-lock output and the stale-lock-clearing output.
- Added docs-derived maintenance prune success-field contracts for `backup prune` and `cache prune`, including parser support for command headings with parenthesized required selectors and coverage for repeated pruned backup paths, selected cache kinds, and audit ids.
- Clarified the CLI spec audit-show field name as `sanitized metadata`, synchronized the Chinese audit-show schema with the English field order, and added docs-derived `audit list`/`audit show` success-field contracts over a real backup-prune audit event.
- Split the source lifecycle CLI spec into machine-checkable `source import`, `source archive`, `source unarchive`, and `source remove` field schemas, synchronized the expanded Chinese source section, and added docs-derived contracts covering empty/local/Git import origins, `SOURCE_EMPTY_AFTER_FILTER` and `TRACKED_SENSITIVE_SOURCE_FILE` warning output, archive/unarchive timestamps plus retained `audit show` metadata, blocker-free dry-run removal, actual source removal with persisted source-row deletion, and `audit show` metadata for removed Git source refs.
- Added docs-derived `catalog skydiscover add`, `catalog skydiscover show`, `catalog skydiscover update`, and `catalog skydiscover remove` success-field contracts using a local Git upstream fixture, covering pinned commit changes and audited add/update/remove output without network access.
- Aligned the CLI spec for `project validation archive|unarchive` with the actual `archived at`/`unarchived at` and `audit id` fields, clarified validation remove's repeated `blocker` label, and added docs-derived contracts for archive/unarchive `audit show` metadata, dry-run remove, actual remove on a dependency-free validation row, and `audit show` metadata retaining deleted artifact/log and filesystem-target counts.
- Split the experiment archive/unarchive CLI spec into explicit `archived at` and `unarchived at` schemas, synchronized the Chinese spec, and added a docs-derived `exp archive`/`exp unarchive` contract over a real experiment worktree.
- Expanded the project lifecycle CLI spec with explicit project remove count fields and repeated `blocker`, synchronized the Chinese archive/unarchive timestamps, and added docs-derived `project archive`, `project unarchive`, and archived-project `project remove --dry-run --cascade` contracts with dynamic repeated filesystem path/planned-trash labels.
- Added retained audit metadata for project and experiment archive/unarchive lifecycle events, recording previous/resulting status and the transition timestamp, with docs-derived contracts resolving real events through `audit list` and `audit show`.
- Expanded the experiment remove CLI spec with explicit deleted run/artifact/log/annotation count fields and repeated `blocker`, synchronized the Chinese schema, and added a docs-derived archived-experiment `exp remove --dry-run --cascade` contract with dynamic repeated filesystem path/planned-trash labels.
- Added docs-derived experiment worktree lifecycle contracts for `exp worktree remove` dry-run/actual output and `exp worktree restore`, including retained `audit show` metadata for worktree remove/restore and raw-token write/non-rendering assertions across restore; also added experiment token contracts for `exp token list`, `exp token regenerate`, and `exp token revoke`, including raw-token non-rendering assertions and retained `audit show` metadata for token regenerate/revoke.
- Extended the docs-derived `exp create` contract with the same raw-token write/non-rendering assertion, proving initial worktree token creation writes `.alab/token` without printing the raw token.
- Added a docs-derived `exp create --source-ref` success-field and lineage contract, proving explicit existing-source selection follows the canonical output field order, reuses the selected source without creating an inline source row, records source-origin metadata, and keeps raw worktree tokens out of stdout.
- Added docs-derived `exp create` success-field contracts for inline local, Git, and empty source origins, proving each `--source-*` bootstrap path follows the canonical field order, creates a source-backed experiment, writes the token path, and keeps raw worktree tokens out of stdout.
- Added a docs-derived `exp create --from-exp` success-field and lineage contract, proving from-experiment creation follows the canonical output field order, writes but does not print the child worktree token, reuses the parent source without creating a new source row, and records `creation_origin.kind = from_exp` metadata.
- Added docs-derived inspection checkout contracts for `exp checkout` and `exp checkout remove` dry-run/actual output, including conditional path/trash field coverage and strict raw inspection-token write/non-rendering assertions.
- Extended the `exp checkout remove` contract through `audit show`, proving retained audit metadata includes token revocation/hash details without leaking raw inspection tokens or the original absolute checkout path.
- Extended the `exp checkout` create contract through `audit show`, proving retained add metadata records the inspection token id, pinned commit, path registry id, and created-for path hash without leaking raw inspection tokens or the checkout path.
- Added a docs-derived `submit` success-field contract over a real reusable passed run, proving accepted submission output follows the CLI spec field order and keeps the final run/commit, stored-summary flags, closed experiment status, and repeated `ref` rendering aligned.
- Clarified the annotation remove CLI spec to render blockers as explicit repeated `blocker` fields, synchronized the Chinese schema, and added docs-derived annotation contracts for `annotate add`, `annotate edit`, `observe annotations list|show --history`, `annotate archive`, `annotate unarchive`, archive/unarchive `audit show` metadata, and `annotate remove` active-blocker/dry-run/actual output.
- Split the observe run/artifact/log CLI spec into explicit `list|show|export`, `archive`, `unarchive`, and `remove` success-field schemas, synchronized the Chinese observe summary, and extended docs-derived contracts to run archive/unarchive plus artifact/log export and archive/unarchive output over real captured files.
- Added retained audit metadata for observe run/artifact/log archive and unarchive events, then extended the docs-derived run/artifact/log contracts through `audit show` to verify previous/resulting archive status and transition timestamps.
- Added docs-derived observe remove contracts for artifact/log active-blocker dry-runs, archived dry-runs, and actual removals, plus run `--cascade` dry-run/actual removal after archived dependent logs, including dynamic repeated filesystem path and planned trash move labels.
- Extended those observe remove contracts through `audit show`, proving actual artifact/log/run removals retain sanitized filesystem target metadata and run dependent/latest/final-run metadata.
- Extended docs-derived read/diagnostic contracts to `project list`, `context show`, and `context repair`, binding project inventory and marker repair output to the canonical CLI spec field order.
- Extended the `context repair` contract through `audit list` and `audit show`, proving retained repair metadata records repair mode, registry id, old/new path hashes, row-creation status, and timestamp without leaking raw paths or credentials.
- Extended the docs-derived experiment observe contract from list/show to include `observe experiments search` and `observe experiments best`, using a real passed run so best output is non-empty and follows the shared experiment result schema.
- Fixed the CLI spec primary object-type table so `project init` is explicitly listed as a `project` result object in both English and Chinese docs.
- Added an all-commands help schema contract proving `help --all --explain` covers every registered command exactly once with stable `help` and `help_command` field ordering and registry-backed summaries.
- Added a runtime preflight matrix proving every non-global-public registered command fails as `COMMAND_UNAVAILABLE` without context/key/home, emits the stable error schema, and does not create `ALAB_HOME`.
- Expanded the locked-command preflight matrix with handler-level argument payloads such as unsupported options, `--value-file`, `--body-file`, submit summary/feedback files, `--config`, `--out`, and `--out` under a missing parent directory, proving unavailable commands still fail before command-specific parsing, file reads, file writes, output-parent creation, or home creation.
- Added a matching nested-help payload matrix proving selected `--help --explain` requests use the same locked capability decision when handler-level payload arguments are present, while still avoiding file reads, output writes, output-parent creation, and home creation.
- Added runtime nested-help and top-level all-help matrices proving every non-`help` registered command can render selected `--help` and `--help --explain` output with stable field ordering, registry-backed summaries, no-context availability values, locked reasons, unlock hints, capability sources, and no `ALAB_HOME` creation.
- Covered both `help --all --explain` and `--help --all --explain` through the actual CLI entrypoint, ensuring all registered commands appear exactly once with the same no-context availability contract used by selected nested help.
- Added default-help runtime coverage for no-command `alab`, `alab help`, and `alab --help`, proving locked commands are hidden, global-public rows stay in registry order, field ordering remains stable, and help display does not create `ALAB_HOME`.
- Promoted the central help-schema contract to parse `help` and `help_command` field ordering directly from `docs/spec_cli.md`, so future CLI spec edits cannot drift from top-level/default help rendering.
- Added capability-surface registry contracts so resolver path sets cannot reference unregistered commands, global public commands remain unauthenticated, observe read/lifecycle commands remain token-or-admin, and status/run/submit/public experiment creation keep their expected credential surfaces.
- Added a runtime read-alias equivalence contract proving `exp`/`observe experiments`, `runs`/`observe runs`, `artifacts`/`observe artifacts`, `logs`/`observe logs`, and `annotations`/`observe annotations` read/export aliases render identical structured stdout over the same saved project data.
- Added runtime lifecycle-alias coverage for `runs`, `artifacts`, and `logs` top-level archive/unarchive/remove aliases, proving remove dry-runs are byte-identical to their canonical `observe ... remove` forms and archive/unarchive aliases render the canonical docs-derived field order.
- Added a strict text-renderer contract to the CLI contract suite, locking object-block separation, warning blocks after primary results, repeated list labels, nullable `none`, literal user text `none`, and empty multiline `[empty]` rendering.
- Added a CLI-level `--output rich` contract proving prefix and trailing global placement render the same result data as text output, do not persist `rich` into global config, and that persisted `output.format = "rich"` remains rejected.
- Added a CLI-level `--key-stdin` validation matrix proving empty input, lone newline, embedded newlines, NUL bytes, extra trailing newlines, duplicate `--key-stdin`, and both `--key`/`--key-stdin` orderings fail with stable `CONFIG_INVALID`, while a single trailing newline is stripped for valid root authentication.
- Added a root/admin not-found contract proving run, validation, artifact, log, annotation, credential, audit, and missing SkyDiscover catalog selectors render precise object-specific `*_NOT_FOUND` error blocks with exit `2`, while the documented `CACHE_NOT_FOUND` mapping remains reserved at exit `2`.
- Added a CLI-level complete-id contract proving abbreviated ALab object selectors for project, source, experiment, validation, run, artifact, log, annotation, credential, and audit fail with stable `CONFIG_INVALID`/`object ids must be complete` output instead of being treated as object-specific lookups.
- Added a CLI-level RFC 3339 time-filter matrix covering audit, experiment, run, artifact, log, and annotation filters, proving missing offsets and malformed timestamp shapes fail with stable `CONFIG_INVALID` while numeric offsets are accepted.
- Added a CLI-level debug-mode contract proving internal system failures print traceback only under `ALAB_DEBUG=1`, normal mode keeps the stable error block only, debug tracebacks do not expose local/env secret sentinel values, and ordinary `CONFIG_INVALID` failures do not emit tracebacks even in debug mode.
- Added a docs-derived error-exit mapping contract that compares the English and Chinese CLI specs to the implementation table, verifies every documented code through runtime lookup, and enforces the V1 rule that future `*_NOT_FOUND` codes default to exit `2` while unknown internal codes default to exit `5`.
- Added a CLI-level `HOME_EXISTS`/`OUTPUT_EXISTS` contract covering initialized and non-empty unrelated homes plus config/artifact/log export targets, proving stable error blocks, preserved existing output bytes, and successful `--overwrite` recovery paths.
- Added a reusable storage JSON contract validator for persisted JSON objects, with tests for schema version, required keys, unknown keys, and non-object rejection.
- Applied the JSON contract validator to runtime capability details and SkyDiscover catalog metadata reads, and aligned stored SkyDiscover catalog metadata to the documented safe key set (`safe_summary`, `task_refs`, `evaluator_refs`, and `warnings`).
- Aligned generated cache entry metadata with the documented safe cache JSON contract, storing `safe_summary`, `inputs_hash`, and `warnings` in `metadata_json` while keeping Docker tags and Python environment paths in their dedicated columns and clearing legacy cross-column values during cache hits.
- Aligned credential metadata reads and writes with the documented safe credential JSON contract, including default admin/token metadata generation, unknown-key rejection after successful credential verification, and inspection checkout self-repair relying on the marker-pinned commit instead of storing `inspection_commit` in credential metadata.
- Aligned source origin metadata reads and writes with the documented safe origin JSON contract, adding per-origin `origin_id` values, enforcing primary-origin/origins consistency, and rejecting unknown origin keys before source display or dedupe metadata updates.
- Aligned annotation target and visibility JSON reads/writes with the documented annotation JSON contracts, including fixed-key target payloads, path/line target shape checks, private-visibility creator requirements, and project-visible rows that no longer persist a null `creator_exp_id`.
- Aligned experiment metadata reads and writes with the documented experiment metadata JSON contract, including fixed creation-origin variants for source, inline-source, and from-experiment creation, display safe-summary validation, and validated metadata use in experiment listing, search, sorting, and result rendering.
- Aligned experiment policy reads and writes with the documented experiment policy JSON contract, including optional mutable overrides, normalized visibility experiment-id storage, and validated policy use in mutable-scope checks plus token/public visibility calculations.
- Aligned run and validation record reads and writes with the documented execution record JSON contract, including config hash recording, finite numeric metrics, warning arrays, sanitized stale-interruption metadata, sanitized mutable-scope diagnostics, and validated observe run filtering/rendering.
- Aligned audit deleted-id and metadata writes plus audit show rendering with documented audit JSON contracts, including normalized deleted-id count/id maps, fixed safe audit metadata keys, and strict top-level unknown-key rejection for future audit metadata additions.
- Aligned final submission refs writes with the documented submission refs JSON contract, preserving first-seen ref order while enforcing the single-`none` form or deduplicated complete experiment id refs.
- Aligned stored project config reads and writes with the documented `project_config_versions.canonical_config_json` contract, including the `git` section, strict top-level keys, stored secret marker object shape, and canonical fingerprint retention for imported secret markers.
- Added fail-closed `.alab/context.json` marker contract validation for detection, repair, marker writing, and token regeneration, enforcing marker version, known keys, context-specific ids, project repo hashes, inspection commits, and optional repair timestamps.
- Added a generated runtime unknown-option matrix for every registered non-help command, using explicit root/admin credentials or an experiment worktree token as needed, and asserting `CONFIG_INVALID` unsupported-option failures leave the full SQLite snapshot, global config, context markers, and worktree token files unchanged.
- Added a global-option placement contract proving `--home`/`--key` work both before and after command paths, including top-level observe aliases, while standalone `--` stops global pre-scan before later global-looking tokens.
- Locked `--all` help ordering so available commands render before locked commands while preserving registry order within each group.
- Added a global-public unsupported-option runtime matrix covering `help`, `--help`, `auth init`, global config repair/diagnostic commands, and context diagnostics/repair, proving unsupported command options fail with stable `CONFIG_INVALID` output before any `ALAB_HOME` directory is created.
- Added an ambient-key help/capability runtime matrix proving a valid `ALAB_KEY` does not broaden no-command help, `help`, `--help`, top-level `--all --explain`, or selected nested help output; the same selected command remains locked with ambient credentials but becomes available with explicit `--key`, and handler payload files are still not touched during help rendering.
- Added an explicit-root help/capability runtime matrix for both `--key` and `--key-stdin`, proving root credential display follows registry credential classes, keeps token-only commands locked without an experiment worktree context, preserves stable command ordering, and renders `explicit-root`/`root` credential metadata.
- Added an explicit-admin help/capability runtime matrix for both `--key` and `--key-stdin`, proving project admin display follows registry credential classes, keeps root-only and token-only commands locked, preserves stable command ordering, and renders `explicit-admin`/`admin` credential metadata.
- Tightened capability preflight for project admin keys so selected help and direct execution with a mismatched explicit `--project` are locked as `COMMAND_UNAVAILABLE` before handler authentication, while same-project selected help remains available with `project-admin` capability source.
- Added a project-context help/capability runtime matrix proving public project contexts expose only global-public plus public project commands by default, render safe locked rows under `--all --explain`, and switch to the matching admin/root command surfaces with stable credential metadata when explicit keys are supplied from the project directory.
- Added an experiment-context help/capability runtime matrix proving worktree-token help exposes global-public, public project experiment creation, and experiment/observe token commands by default, renders safe locked rows under `--all --explain`, keeps selected public `exp create` help side-effect free, and switches to admin/root surfaces with `run`/`submit` still sourced from `worktree-token` when explicit keys are supplied from the experiment worktree.
- Tightened explicit admin/root capability source rendering in experiment contexts so token-only `run` and `submit` rows report `worktree-token` when a valid worktree token is what makes them available.
- Added an inspection-context help/capability runtime matrix proving inspection-token help exposes only global-public, visible observe read/export commands, status, and inspection checkout removal by default; selected/direct `submit` remains locked before handler file reads, and explicit admin/root keys switch to the project admin/root surfaces while token-only `run`/`submit` stay unavailable from inspection checkouts.
- Added an explicit-key context-conflict runtime matrix for both `--key` and `--key-stdin`, proving admin/root keys in experiment and inspection contexts cannot use a mismatched explicit `--project`; selected help renders the safe conflict reason/source, direct execution fails with `CONTEXT_CONFLICT`, and handler output files are not created.
- Added a context-local `--key-stdin` equivalence matrix proving project, experiment, and inspection help/capability output is byte-for-byte identical to `--key` for the same admin/root credential across default help, `help --all --explain`, and `--help --all --explain`.
- Added a context-local read-command `--key-stdin` equivalence matrix proving side-effect-free project reads (`project show` and `project config show`, with and without explicit `--project`) produce byte-identical output to `--key` across project, experiment, and inspection contexts for both admin and root credentials.
- Split the `status` CLI spec into project/public, experiment/inspection, and public-invalid field schemas, then extended runtime coverage to prove each context renders the correct object type and docs-derived field order.
- Added a known-option coverage contract proving every literal option read inside guarded service functions, plus shared helper option reads for project selection, lifecycle reason, force confirmation, secret input, and annotation body/privacy selectors, is present in that function's `require_known_options` allowlist.
- Added a docs-derived command-option acceptance contract that parses canonical command syntax and explicit option-contract lines from `docs/spec_cli.md`, then requires each documented command option to be accepted by the registered handler or guarded helper while ignoring prose references to other commands.
- Extended the documented command-option acceptance contract to `docs/spec_cli_cn.md`, including Chinese full-width-colon contract-line prefixes, so Chinese-only option claims also fail when the registered handler surface does not accept them.
- Synchronized the Chinese CLI spec's machine-readable command headings and option-contract lines with the English CLI spec for global config, validation remove, experiment create/remove/checkout/worktree/token, and annotation mutation surfaces, then added a direct English/Chinese documented-option equivalence contract.
- Extended CLI spec command-surface parsing to combine machine-readable command headings, primary object-table paths, and registered command mentions, then added a direct English/Chinese surface coverage contract requiring both CLI specs to cover exactly the registered command paths.
- Generalized docs-derived success-field parsing to read either CLI spec, synchronized selected Chinese success-field lines with English for help/auth/config/config-validate/key/context/project/env/secret/source/catalog/experiment/token/tag/run/submit/observe/annotation/status surfaces, including object/scope variants, and added a selected English/Chinese success-field equivalence contract.
- Extended the representative root/admin object-specific not-found matrix to cover project, source, and experiment selectors in addition to run, validation, artifact, log, annotation, credential, audit, and catalog selectors, and now assert each not-found failure leaves the full SQLite snapshot and global config unchanged; the representative incomplete-object-id selector matrix now makes the same no-DB/no-config-side-effect assertion.
- Extended the CLI-level RFC 3339 invalid-time-filter matrix and representative `HOME_EXISTS`/export error matrix to assert no SQLite snapshot or global config changes occur on rejected initialized homes, invalid time filters, existing export targets, or missing artifact/log export parents; non-ALab non-empty homes also remain untouched, existing export targets preserve their output-file bytes, and missing export-parent failures create neither parent directories nor output files.
- Converted the remaining unsupported-option hardening from a manual audit into a repeatable default-suite check for future command additions.
- Added a generated force-confirm guard matrix for every hard-remove command using `require_force_confirm`, proving missing `--force`, missing `--confirm`, and mismatched confirm values fail with stable `CONFIG_INVALID` errors while preserving SQLite rows, marker files, token files, and removal target paths.
- Added a generated dry-run no-write matrix for dry-run-capable hard-remove commands, covering project, validation, source, experiment, worktree, inspection checkout, run, artifact, log, and annotation removal; each dry-run now asserts `dry run: true`, `removed: false`, `audit id: none`, and preserves the full SQLite snapshot, marker/token files, removal target paths, and home trash tree.
- Added a generated lifecycle-blocker no-write matrix for actual forced hard-remove attempts against active project, validation, source, experiment, run, artifact, log, and annotation targets, proving `RESOURCE_BUSY` blockers preserve the full SQLite snapshot, marker/token files, removal target paths, and home trash tree before any staging or mutation runs.
- Added a generated dependency-blocker no-write matrix for actual forced validation, source, and run removals after the target has been archived, covering both `dependent_records_require_cascade` and `dependent_records_not_archived`; the matrix preserves the full SQLite snapshot, marker/token files, target paths, project tree, home trash tree, and source Git ref commit.
- Enforced the lifecycle spec's mutually exclusive hard-remove mode contract: `--dry-run` now conflicts with `--force` and `--confirm` across dry-run-capable hard-remove commands, with a generated no-side-effect matrix proving mixed planning/destructive modes fail with `CONFIG_INVALID` before DB, marker/token, path, project tree, or trash changes.
- Synchronized the CLI specs with the lifecycle remove-mode conflict rule and added a static service contract requiring every `require_force_confirm` handler/helper that also accepts `--dry-run` to call the mixed-mode guard.
- Added a docs-derived mixed-mode conflict declaration contract that scans both CLI specs for every documented `(--dry-run|--force --confirm ...)` remove surface and requires the corresponding `Conflicts` lines to name `--dry-run`, `--force`, and `--confirm`.
- Added a docs-derived English/Chinese conflict-option synchronization contract for CLI specs and synchronized Chinese conflict lines for config export/import/set, cache prune, experiment token selectors, and submit refs.
- Added a docs-derived stable error-code catalog and numeric exit-code table contract, proving the English and Chinese error-code lists, exit mapping tables, numeric exit categories, and implementation constants remain synchronized.
- Added a docs-derived warning-code catalog contract, documented the implemented `DOCKER_SETUP_OUTPUT_CAPTURED` Docker setup-output warning in the CLI/runner/test specs, and now require every implemented stable warning code to be listed in both CLI specs.
- Implemented the V1 `.alab/token` permission warning path: token-context command output now appends `TOKEN_FILE_PERMISSIONS` after the primary result when the token file is broader than `0600`, without rewriting the user's file permissions.
- Added a CLI token-write contract covering experiment creation, inspection checkout, worktree restore, and token regeneration, proving raw token files are written with `0600` permissions and `.alab/` Git exclude rules are present; token regeneration now refreshes the exclude rule if it was removed.
- Added a generated runtime global-option pre-scan error matrix for every registered command and alias, proving duplicate global options, missing global values, invalid `--output` values, and `--key`/`--key-stdin` conflicts fail with stable `CONFIG_INVALID` output before home creation, command matching, credential verification, or handler execution.
- Added a generated runtime trailing-global placement matrix for every registered non-help command and alias, proving trailing `--home`, `--key`, and `--output text` are consumed by global pre-scan before handler unsupported-option validation and leave SQLite rows, global config, context markers, and worktree token files unchanged.
- Added a generated runtime standalone-separator matrix for every registered non-help command and alias, proving global-looking tokens after `--` are not consumed by global pre-scan, do not read `--key-stdin`, do not switch the selected home, and leave SQLite rows, global config, context markers, token files, source/catalog trees, export targets, and would-be worktrees unchanged.
- Added a generated runtime explicit-credential unavailable-command matrix for `--key` and `--key-stdin`, proving root credentials cannot run token-only commands outside experiment worktree contexts and admin credentials cannot run root-only or token-only commands before handler option parsing, missing payload file reads, output writes, output-parent creation, SQLite mutation, global config/context marker/token mutation, Git operations, runner execution, or filesystem staging.
- Added a generated runtime project-context unavailable-command matrix, proving every registered command outside the public project surface fails with stable `COMMAND_UNAVAILABLE` output before handler option parsing, missing payload file reads, output writes, output-parent creation, SQLite mutation, global config/context marker/token mutation, Git operations, runner execution, or filesystem staging.
- Added a generated runtime experiment-context unavailable-command matrix, proving every registered command outside the worktree-token surface fails with stable `COMMAND_UNAVAILABLE` output before handler option parsing, missing payload file reads, output writes, output-parent creation, SQLite mutation, global config/context marker/token mutation, Git operations, runner execution, or filesystem staging.
- Added a generated runtime inspection-context unavailable-command matrix, proving every registered command outside the inspection-token surface fails with stable `COMMAND_UNAVAILABLE` output before handler option parsing, missing payload file reads, output writes, output-parent creation, SQLite mutation, global config/context marker/token mutation, Git operations, runner execution, or filesystem staging.
- Tightened command-local duplicate option validation for source/project initialization paths, project secret input, secret GC, experiment creation/best/token selectors, submit stdin flags, log hidden access, and annotation body/target/privacy inputs so singleton options fail before writes, file exports, runner execution, or lifecycle audit rows.
- Added a static singleton-option contract requiring every known command option to be either duplicate-guarded or explicitly classified as a repeated option; future command additions now fail the default suite if they add an unclassified singleton option.
- Added runtime coverage proving `logs show --include-hidden --include-hidden` fails with `CONFIG_INVALID` before log lookup side effects and leaves SQLite plus global config unchanged.
- Added a representative runtime singleton-duplicate matrix covering project init, source import, experiment create/best/token selectors, project secret set/GC, submit stdin flags, logs show, and annotation add/edit, proving duplicate singleton options fail with stable `CONFIG_INVALID` before DB/config/marker/token changes or missing body/value/config file reads.
- Added a generated runtime duplicate-option matrix for every registered command-local singleton option, including helper-backed observe lifecycle and annotation status aliases, proving duplicates fail with stable `CONFIG_INVALID` before availability fallback, selector lookup, file reads, DB/config/marker/token writes, filesystem staging, runner execution, or lifecycle audit rows; lifecycle remove `--reason` guards now run before project/selector lookup.
- Added generated registered-command success-field documentation contracts: every registered command must now resolve to documented CLI success fields directly, through object/scope variants, or through its canonical alias handler, and the resolved English/Chinese field contracts must stay synchronized.
- Fixed the Chinese CLI spec for `project config set` so it explicitly inherits the `project config import` success/exit contract instead of relying on prose.
- Hardened value-taking option parsing so both global and command-local options reject missing values when the next token is another `--...` option, then added representative no-side-effect runtime coverage across global parsing, config export, source import, experiment creation/tags/tokens, log export, annotation targets, submit file inputs, and SkyDiscover catalog add.
- Added a generated runtime missing-value matrix for every registered command-local value option, proving absent option values fail with stable `CONFIG_INVALID` errors before availability fallback, mutually exclusive relationship validation, file reads, DB/config/marker/token writes, filesystem staging, runner execution, or lifecycle audit rows; public `status --project` preflight now reports the malformed missing value instead of falling through to `COMMAND_UNAVAILABLE`.
- Tightened project config/env/secret mutation preflight so `--dry-run` with `--skip-baseline-test` fails before config or secret payload file reads, validation writes, SQLite mutation, context marker mutation, or runner execution, then added a runtime no-side-effect matrix covering config import/set, env set/unset, and secret set/unset.
- Added a runtime documented non-remove conflict matrix covering key root/project scope, SkyDiscover ref/commit selectors, backup/cache prune selectors, source import/show selectors, experiment source/from-exp selectors, experiment token selectors, submit refs, and annotation body/target selectors, proving stable `CONFIG_INVALID`/`SOURCE_INVALID` errors without SQLite, global config, marker/token, source/cache tree, worktree, or missing payload-file side effects.
- Extended the opt-in real Docker suite with Harbor separate verifier execution for both `[verifier].image` and `tests/Dockerfile`, proving real containers report `verifier mode: separate`, parse Harbor rewards, preserve hidden verifier stdout, and record Harbor Dockerfile image-cache metadata without making the default suite depend on Docker.
- Extended the default fake-Docker Harbor runner suite with separate verifier image execution and separate `tests/Dockerfile` build/cache coverage, proving `verifier_mode = separate`, visible summary rendering, hidden stdout capture/redaction, Harbor env injection, network mapping, bundle mounts, and Dockerfile cache metadata without requiring Docker in the default suite.
- Extended the static CLI option audit so literal `command_args(...)` reads are included in known-option coverage, and added a value-option registry contract requiring every literal `command_arg(...)` or `command_args(...)` read to be registered for positional parsing and missing-value validation.
- Added a registered-command positional grammar contract requiring every non-help command handler to validate positional arguments through the shared fixed-count or optional-selector helpers, either directly or through the documented lifecycle helper path.
- Extended the same static option-read audit to helper-mediated literal reads for pagination, sorting, source selection, visibility/mutable policy overrides, credential selectors, typed filters, and time filters so future handlers cannot read an option through a helper without declaring it in the known-option allowlist and value-option registry.
- Extended the singleton duplicate-option audit to helper-mediated source limit value parsing so future source-limit handlers inherit duplicate-guard coverage from the shared parser classification.
- Added a generated runtime extra-positional matrix for every registered zero-positional command, proving surplus positional arguments fail with stable `CONFIG_INVALID` errors while preserving SQLite rows, global config, context markers, token files, source/cache/project worktrees, export targets, and would-be experiment worktrees.
- Added a generated runtime extra-positional matrix for every registered single-selector command, including helper-backed observe and annotation lifecycle aliases, proving surplus positional arguments fail before selector lookup, file export, token/path mutation, lifecycle audit writes, or filesystem staging.
- Added a generated runtime missing-selector matrix for every registered required single-selector command, proving absent object selectors fail with stable object-specific `*_NOT_FOUND` errors before SQLite mutation, global config or marker/token changes, file exports, inspection checkout creation, source/cache tree changes, or lifecycle audit rows.
- Added a generated runtime extra-positional matrix for every registered fixed-count positional command, proving surplus positional arguments fail before global config writes, project/source initialization, secret file reads, project config-version writes, experiment tag mutation, or audit writes.
- Added a generated runtime missing-positional matrix for every registered fixed-count positional command, proving absent required positional arguments fail with stable `CONFIG_INVALID` errors before global config writes, project/source initialization, secret file reads, project config-version writes, experiment tag mutation, or audit writes.
- Tightened source-limit parsing across `project init`, `source import`, and `exp create` so malformed `--max-files`, `--max-total-bytes`, and `--max-file-bytes` values fail before source staging or project/source/config/admin credential writes; `project init` now enforces the same source-limit ceiling on the staged initial source before writing project rows.
- Added a generated runtime typed-value matrix for registered commands using shared pagination, source-limit, integer, numeric, and boolean parsers, proving malformed values fail with stable `CONFIG_INVALID` errors without SQLite, config, marker/token, source/tree, export, or worktree side effects.
- Extended the generated typed/structured-value matrix to sort fields, choice filters, and RFC 3339 time filters, proving malformed `--sort`, choice-style `--status`, and helper-mediated time-filter values fail with stable `CONFIG_INVALID` errors without state changes.
- Extended the same matrix to retention count/day parsing for `backup prune` and `cache prune`, including `--keep` and `--older-than`, so malformed retention values fail before backup deletion, cache pruning, or audit writes.
- Extended the generated typed/structured-value matrix to option-based ALab object id filters, including experiment source filters, token selectors, observe exp/run/validation filters, and audit actor filters; annotation creation now validates target ids and `--private-to-exp` ids before body-file reads or body storage.
- Tightened annotation list filters so object-backed `--target-id`/`--target` values and `--created-by` values must be complete ALab object ids before annotation queries run, while preserving path/line target-id filtering and valid creator experiment filtering.
- Tightened untyped `audit list --object-id` so it now accepts only complete ALab ids or the stable audit literals `backups`, `cache`, and `skydiscover`, with generated no-side-effect coverage proving malformed short ids fail before audit queries.
- Tightened `audit list --action` to the documented generic audit action set, so unsupported action filters now fail with stable `CONFIG_INVALID` before audit queries instead of returning an empty success result.
- Tightened `audit list --object-type` to the documented audit object-type set, so unsupported object-type filters now fail with stable `CONFIG_INVALID` before audit queries and before object-id filter interpretation.
- Tightened `runs list --commit` so commit filters must be hexadecimal commit SHA prefixes and now match stored full commit ids by prefix; arbitrary moving refs such as `HEAD` fail with stable `CONFIG_INVALID` before run record scans instead of returning an empty success result.
- Tightened `runs list --runner-type` to the V1 runner config type set `local`, `docker`, `harbor`, `skydiscover_docker`, and `skydiscover_python`, so unsupported runner filters fail with stable `CONFIG_INVALID` before run record scans instead of returning an empty success result.
- Tightened `artifacts list --root` to the storage-defined artifact roots `workspace` and `run`, so unsupported artifact root filters fail with stable `CONFIG_INVALID` before artifact queries instead of returning an empty success result.
- Tightened `artifacts list --content-hash` to the stored artifact content-hash shape `sha256:<64-hex>`, so malformed hash filters fail with stable `CONFIG_INVALID` before artifact queries instead of returning an empty success result.
- Tightened `logs list --stream` to the storage-defined stream set `stdout`, `stderr`, `hidden_stdout`, and `hidden_stderr`, so unsupported log stream filters fail with stable `CONFIG_INVALID` before log queries instead of returning an empty success result.
- Tightened `exp token list|revoke|regenerate --mode` to the shared token-mode choice set `worktree|inspection`, so malformed token-mode selectors now fail with the generated typed-value no-side-effect contract before token queries or regeneration writes.
- Tightened `exp create --visibility-scope` to the documented visibility scope set `none|same_project|explicit`, added it to the generated typed-value no-side-effect contract, and made the CLI specs list the concrete mutable/visibility options instead of relying on prose.
- Tightened experiment list/search/best `--status` to the shared experiment status set `open|closed|archived`, documenting the accepted values and routing malformed values through the generated typed-value no-side-effect contract.
- Tightened `key create --role` to the shared key-role choice set `admin`, documenting the accepted value and routing malformed roles through the generated typed-value no-side-effect contract before admin credential writes.
- Tightened `catalog skydiscover add|update --commit` to validate the documented full-SHA shape before catalog clone/fetch/update work, and added the malformed selector to the generated typed-value no-side-effect contract.
- Tightened `exp create --from-commit` and `exp checkout --commit` so malformed non-SHA custom selectors fail through a shared commit-selector parser before experiment inheritance lookup, checkout path registration, worktree creation, or audit writes, and added both selectors to the generated typed-value no-side-effect contract.
- Extended the generated typed-value contract from malformed types to invalid numeric ranges for retention, pagination, and audit pagination values, including negative `--keep`/`--older-than`, out-of-range observe `--limit`, negative observe `--offset`, and invalid audit `--limit`/`--offset`.
- Moved `backup prune --keep` parsing ahead of backup file enumeration so malformed or negative keep counts fail before backup glob/stat work, deletion decisions, or audit writes.
- Extended the generated source-limit typed-value contract to negative `--max-files`, `--max-total-bytes`, and `--max-file-bytes`, proving `project init`, `source import`, and inline `exp create` reject invalid limits before source staging or persistence work.
- Moved public inline source policy-ceiling validation ahead of temporary source work creation, so no-key callers who raise limits above `[public_source_import]` fail before source path reads, copies, Git clones, source rows, experiment rows, or worktree creation.
- Tightened artifact list `--size-min` and `--size-max` filters to non-negative integer byte counts, documenting the bounds and adding them to the generated typed-value no-side-effect contract before artifact queries run.
- Tightened `--config-version` observe filters and project config `--version <n>` selectors to positive retained config version numbers, with generated no-side-effect typed-value coverage for experiment/run observe filters and smoke coverage for project config reads before selector lookup.
- Tightened observe numeric range filters so inverted `--reward-min`/`--reward-max` pairs on experiment and run lists, and inverted `--size-min`/`--size-max` pairs on artifact lists, fail with `CONFIG_INVALID` before query execution instead of silently returning empty results.
- Tightened time range filters so inverted matching `after`/`before` pairs for audit, experiment, run, artifact, log, and annotation lists fail with `CONFIG_INVALID` before query execution, while preserving the existing RFC 3339 offset and malformed timestamp checks.
- Tightened export output path validation so `project config export`, `artifacts export`, and `logs export` reject directory targets with stable `OUTPUT_EXISTS` even when `--overwrite` is supplied, instead of falling through to filesystem write errors.
- Tightened `exp create` default worktree path validation so an already-existing default path, including an empty directory, fails with stable `OUTPUT_EXISTS` and a `--path` next action before source import, worktree creation, token writes, path registration, or experiment rows; explicit custom `--path` still accepts an empty directory.
- Tightened text input file handling for `--value-file`, `--summary-file`, `--feedback-file`, and `--body-file` so missing, directory, unreadable, or non-UTF-8 targets fail with stable `CONFIG_INVALID` instead of falling through to internal file errors, before secret writes, submission rows, annotation rows, runner execution, or lifecycle audit rows.
- Tightened local runner sanitized environment setup so `env_mode = "sanitized"` creates the operation temporary `home/` directory before process start while preserving inherited `ALAB_*` credential stripping and injected internal `ALAB_*` operation variables.
- Tightened local runner and artifact-capture path containment so `runner.working_directory` and resolved artifact paths are checked with normalized path ancestry instead of string-prefix matching, preventing sibling prefix paths from being treated as inside the workspace or artifact root.
- Tightened file reward parsing so `reward.path` accepts only `workspace:` and `run:` roots, rejects normalized or symlink escapes from the selected root, enforces the artifact per-file read limit, parses JSON reward objects by top-level `primary_metric`, and rejects non-finite numeric values.
- Tightened project config schema path validation so `runner.working_directory`, `runner.dockerfile`, `runner.context`, `runner.program_path`, file `reward.path`, and artifact globs reject absolute paths, unsupported artifact/reward roots, and lexical `..` escapes before config persistence or runner execution; source-dependent path existence is still deferred to saved run/validation failures.
- Tightened project config schema limit validation so artifact capture and log byte limits reject zero, negative, and boolean values before reward parsing, artifact capture, or log storage can observe ambiguous limits.
- Tightened stdout-regex reward schema validation so invalid regular expressions and patterns without either a named `reward` group or a capture group fail before runner execution, while runtime parsing now follows the documented `reward`-group-first, first-capture fallback order.
- Tightened project config numeric schema validation so runner timeouts reject booleans and strings instead of coercing them, Docker CPU limits require positive finite numbers, Docker memory limits require positive integers, and public source-import policy limits require non-negative integers.
- Tightened runner command schema validation so explicitly provided `runner.command` lists must contain at least one non-empty argv entry and explicitly provided `runner.shell` values must contain non-whitespace text before runner execution.
- Added runner shell contract coverage across the V1 runner boundary: local shell mode has a direct `/bin/sh` execution test with ALab env injection, Docker shell mode now has fake-Docker argument-shape coverage proving ALab appends `/bin/sh -c <shell>` after the image, and Harbor/SkyDiscover adapter runner configs reject user shell commands before execution.
- Added runner environment isolation contract coverage for the V1 runner boundary: local `env_mode = "full"` now proves host `ALAB_*` credentials are stripped while non-ALab host env is inherited with the documented warning, and Docker runner fake-CLI coverage proves the container env is hostless while internal ALab operation variables override conflicting `[env]` values.
- Added runner input/context isolation coverage: the local runner now has a direct closed-stdin contract test, and a CLI smoke test proves experiment runs execute from a clean temporary runner workspace that cannot see the worktree `.alab/context.json` or `.alab/token` files even though they exist in the experiment worktree.
- Implemented the documented local runner process-group timeout behavior: local runners now start in a separate session, timeout handling sends `SIGTERM` to the process group, waits briefly, then sends `SIGKILL` if needed; regression coverage proves a child process spawned by the timed-out runner does not survive to write after the timeout.
- Aligned `stdout_regex` reward parsing with the documented observable stdout contract: regex rewards now parse the redacted stdout truncated by `logs.stdout_limit_bytes`, so a reward hidden by secret redaction or beyond the stored stdout limit cannot be parsed from otherwise invisible bytes.
- Aligned artifact capture with the documented glob semantics: directory matches now expand recursively into file artifact records, matches from multiple globs are deduplicated by resolved path and sorted by normalized relative path before capture and limit accounting, and symlink escapes are recorded as `skipped` artifact rows instead of being silently dropped.
- Aligned artifact capture error visibility with the V1 warning contract: capture `error` artifact rows now add a stable `ARTIFACT_CAPTURE_ERROR` warning to saved run/validation records, run/show output, project config baseline output, and project validation output without changing execution status.
- Added default-suite warning coverage for the V1 exact-artifact-bytes contract: configurations with active `secret_env` values plus artifact globs now prove `ARTIFACT_BYTES_NOT_REDACTED` is rendered by project init, manual validation, config baseline validation, run, and observe-run output, persisted in validation/run `record_json`, while stdout previews stay redacted and artifact export returns exact bytes.
- Tightened `secret_env` config validation so raw values must be valid single-line secret strings, retain markers reject unknown keys and malformed fingerprints, stored `{secret_value_id, fingerprint}` markers are rejected from user config files, and config-import dry runs now check retain-marker fingerprint mismatches without writing rows.
- Tightened project policy schema validation so public booleans reject string coercion, mutable include/exclude patterns reject empty or multiline entries, explicit visibility lists require complete experiment ids, and non-explicit visibility scopes cannot retain ignored experiment ids.
- Tightened global config validation so manual `config.toml` edits reject boolean `schema_version`, unknown top-level keys, unknown `[output]`, `[storage]`, or `[locks]` fields, and non-table section values instead of silently ignoring them or falling through to internal attribute errors.
- Tightened stored experiment policy JSON validation so mutable policy arrays reject empty include sets and empty/multiline patterns, visibility schema versions reject booleans, explicit visibility requires complete experiment ids, and non-explicit scopes cannot retain ignored id arrays.
- Tightened shared stored JSON contract validation so boolean `schema_version` no longer passes as integer `1`, and added typed validators for runtime capability details, catalog metadata, and cache metadata, including safe-summary, string-array, object, and non-empty inputs-hash checks.
- Tightened annotation target JSON and CLI path-target validation so repo paths must be normalized forward-slash relative paths without absolute, Windows-absolute, empty, `.`, `..`, backslash, NUL, or newline components, line ranges reject boolean start/end values while requiring positive inclusive ranges, object target ids must be complete ids matching their target type, experiment object targets must match `exp_id`, and path/line target ids must match `exp_id:commit:repo_path`.
- Tightened annotation authoring against the V1 experiment-binding contract: validation-owned artifact targets without a resolved experiment id now fail with stable `CONFIG_INVALID` before annotation rows or revisions are stored, annotation add/edit continue to reject active `secret_env` body values, and private annotation visibility/editability no longer expands target visibility for experiment tokens. Collaboration smoke coverage now proves a private annotation that targets a peer experiment becomes hidden and uneditable when current project visibility no longer exposes that peer target, without writing a new revision.
- Tightened annotation storage DDL so annotations now enforce documented target/status/creator enums, positive current revisions, and non-null resolved commits for path/line targets, while annotation revisions enforce positive revision numbers and root/admin/token creators.
- Tightened artifact and log storage DDL so artifact rows enforce documented roots, statuses, owner exclusivity, capture/error payload shape, archive timestamp state, and non-negative sizes, while log rows enforce documented streams, hidden/visible consistency, owner exclusivity, archive timestamp state, boolean flags, and stored byte bounds.
- Tightened run and validation storage DDL so active records cannot retain archived timestamps and non-running execution records must carry `ended_at`, while preserving documented nullable `exit_code` and `reward_value` for runner-start errors, interrupted records, and skipped validations.
- Tightened project/source/experiment storage DDL so project archive status must retain a valid pre-archive state, inherited config versions must point at their inherited validation and non-inherited versions cannot retain one, sources must store the canonical `alab/source/<source_id>` ref, and experiments now enforce documented archive pre-state, closed timestamp visibility, and all-or-none final-run removal metadata.
- Tightened foundation storage DDL so credentials enforce root/admin/token row shape, path registry rows enforce context ownership and active/removed timestamp state, catalogs enforce V1 `skydiscover` key/type/status values, and cache entries enforce V1 kind/status values plus non-negative sizes.
- Tightened audit/secret/submission/tag storage DDL so audit reasons enforce the documented 65536-byte text limit, secret values reject non-text, NUL-containing, and too-short values while requiring HMAC-style fingerprints, submission message/summary/feedback fields enforce documented byte limits, and experiment tags enforce normalized lowercase ASCII slug shape and size.
- Tightened catalog/cache storage DDL and specs so active/removed rows must keep `removed_at` consistent with lifecycle state, Docker image cache rows must store `docker_tag` instead of `path`, and SkyDiscover Python environment plus trash cache rows must store `path` instead of `docker_tag`.
- Implemented the documented experiment run/submit operation lock using the `locks` table: active same-experiment run/submit locks now fail fast with `EXPERIMENT_BUSY`, expired run/submit locks are replaced during acquisition, long runner execution is not wrapped in a SQLite write transaction, and locks are released on success or failure.
- Aligned run lifecycle ordering with the V1 contract: dirty-scope checks now allocate a `running` run row before ALab auto-commit, the auto-commit uses the allocated run id in trailers, full-diff scope failures update that row to `error`, and runner/log/artifact capture now runs outside SQLite write transactions before a final short persistence transaction.
- Tightened ALab auto-commit identity so run-created commits explicitly set both Git author and committer from the experiment's bound `[git]` config, even when the surrounding process environment contains conflicting `GIT_AUTHOR_*` or `GIT_COMMITTER_*` variables.
- Tightened staged-trash and Git-ref transaction failure handling so non-ALab audit/DB failures after filesystem or ref staging now restore staged trash paths and deleted source/experiment refs, then return stable `STORAGE_ERROR` output with the documented repair next action instead of leaking raw internal failures; worktree, source, experiment, inspection checkout, project whole-tree, validation cascade, artifact, log, and run cascade remove now have regression coverage proving DB/token/path rows, Git refs, lifecycle metadata, and filesystem contents remain intact.
- Tightened project-context repair authentication so ambient `ALAB_KEY` may satisfy the documented root/admin path for project marker repairs while experiment and inspection repairs still ignore ambient admin/root keys and require strict self-token branch or pinned-commit checks.
- Tightened public project capability fallback so invalid project status keeps the reduced public-invalid field set under ambient credentials and explicit non-admin keys, while public `exp create` treats valid but nonmatching explicit credentials as public callers when policy permits it and remains hidden/preflight-blocked when `project.allow_public_exp_create = false`.
- Added a generated invalid explicit-credential runtime matrix for every registered command, covering both `--key` and `--key-stdin`, and proving `AUTH_DENIED` occurs before handler option parsing, missing payload-file reads, output-parent creation, SQLite mutation, global config/context marker changes, or filesystem/cache tree changes.
- Added opt-in live SkyDiscover catalog hardening through `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1`: the test probes the official remote, clones and pins `main`, proves `catalog show` does not run Git or fetch the network, discovers a real Python/Docker evaluator ref in the live catalog, and resolves it through `project init skydiscover --source-empty --skip-baseline-test` without adding a default network dependency to the suite.
- Expanded opt-in networked SkyDiscover Python dependency hardening through `ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1`: the evaluator matrix now installs both a direct `six==1.16.0` dependency and a transitive `python-dateutil==2.9.0.post0` dependency set from the configured Python package index with `uv`, imports them inside hidden evaluator environments, verifies reward/feedback capture, and proves per-dependency environment cache hits without changing the existing local-wheel real-environment path.
- Added opt-in native/binary SkyDiscover Python dependency hardening through `ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1`: the evaluator installs a configurable native package from the configured Python package index, defaults to `orjson>=3.10,<4`, imports it inside the hidden evaluator environment, exercises binary serialization/deserialization for metric capture, and proves environment cache hits on a second run.
- Added default-suite saved SkyDiscover Python dependency-failure coverage with a fake `uv`: failed evaluator dependency installation during baseline now creates an invalid project with a saved validation `error` record and `BASELINE_VALIDATION_FAILED` output, while the same failure during `run` creates a saved run `error` record with `RUNNER_ERROR`; both paths exit `1`, keep setup output in hidden logs, and avoid surfacing an internal/system error.
- Added default-suite saved run result-failure coverage for local `RUNNER_FAILED`, `RUNNER_TIMEOUT`, and `RUNNER_ERROR`: the matrix proves each failure exits `1`, renders the normal `run` object fields before appending `error code`, result-level `exit code`, `reason`, and `next`, suppresses debug tracebacks for result failures, persists matching run status/exit/reward-parse/failure metadata, and keeps observe-run rendering aligned with the saved row.
- Added default-suite saved validation result-failure coverage for manual `project validate` failed, timeout, and runner-error records: the matrix proves each saved validation failure exits `1`, renders the documented `validation` object fields before appending `BASELINE_VALIDATION_FAILED`, result-level `exit code`, status-derived `reason`, and `next`, suppresses debug tracebacks, persists matching validation status/exit/reward-parse/failure metadata, and preserves the previous active valid project version and validation id.
- Added default-suite submit result-failure coverage for final-run `RUNNER_FAILED`, `RUNNER_TIMEOUT`, `RUNNER_ERROR`, and missing reusable passed runs: the matrix proves each rejected submission exits `1`, renders the documented `submission` fields before appended diagnostics, keeps the experiment open with no final run/commit and no submission row, saves failed rerun records when a rerun was attempted, and suppresses debug tracebacks.
- Added default-suite baseline result-failure coverage for `project init`, `project config set`, and `project config import` across failed, timeout, and runner-error validation records: the matrix proves each command exits `1`, renders its documented primary object fields before appended `BASELINE_VALIDATION_FAILED` diagnostics, suppresses debug tracebacks, persists matching validation/config/project state, and preserves the previous active valid project version for failed config mutations.
- Fixed `project env set|unset` and `project secret set|unset` baseline result-failure rendering so they preserve appended `BASELINE_VALIDATION_FAILED` fields from the shared config mutation flow instead of dropping them, and added a default-suite matrix for failed, timeout, and runner-error records across all four mutation surfaces, including raw-secret non-rendering checks.

Known incomplete areas:

- These contracts prove registry, alias, primary object-type metadata, selected global-auth/global-config/project/project-lifecycle/config/source/source-lifecycle/catalog/credential/experiment-token/env/secret/experiment/experiment-observe/experiment-lifecycle/experiment-remove/experiment-worktree/inspection-checkout/run/submit/artifact/log/annotation/audit/secret-gc/validation/validation-lifecycle/lock-clear/maintenance-prune/context diagnostics/status success-field ordering, including raw credential one-time rendering rules, raw token write/non-rendering rules, token file private-permission writes, token Git-exclude refresh, token permission warning output, global `config validate` object schemas, observe experiment search/best, observe run/artifact/log archive/unarchive, artifact/log export, run/artifact/log remove dry-run/actual schemas, saved run result-failure output for `RUNNER_FAILED`, `RUNNER_TIMEOUT`, and `RUNNER_ERROR`, saved manual validation result-failure output for failed, timeout, and runner-error records, submit result-failure output for failed/timeout/error final reruns and missing reusable passed runs, `project init`/`project config set`/`project config import` baseline result-failure output for failed, timeout, and runner-error records, `project env` and `project secret` mutation baseline result-failure output with raw-secret non-rendering, and read/export plus lifecycle top-level observe alias behavior; docs-derived stable error-code catalog, numeric exit-code table, exit mapping, warning-code catalog, and representative object-specific not-found selectors; stable `HOME_EXISTS`/`OUTPUT_EXISTS` error blocks for representative write targets; reusable persisted-JSON and context-marker contract validation with project config, credential/audit/source-origin/experiment metadata and policy/submission refs/execution record/annotation target and visibility/runtime capability/catalog metadata enforcement and cache metadata writer alignment; default fake-Docker Harbor shared/separate verifier runner coverage with hidden-log redaction and Dockerfile cache metadata; complete ALab object id enforcement for representative selectors; RFC 3339 time-filter parsing for representative filter families; debug traceback gating for internal failures versus ordinary command errors; context-sensitive status object rendering; capability-surface; ambient-key display isolation; explicit-root/admin display behavior, including project-context repair via ambient `ALAB_KEY` without broadening experiment/inspection self-repair; generated global-option pre-scan error rejection before home creation, generated explicit invalid-credential rejection before handler payloads, generated standalone-separator global pre-scan stop behavior without stdin/home/state side effects, plus global and command-local value-option missing-value rejection, shared typed value-parser malformed-value rejection, including option-looking `--...` next tokens and generated registered command-local absent-value no-side-effect coverage, project config/env/secret dry-run/skip-baseline conflict rejection before payload reads, and documented non-remove conflict rejection without DB/config/marker/token/tree or payload-file side effects, plus static registration coverage for direct/helper-mediated literal value-option reads and registered handler positional validators; `--key-stdin` input validation, display, and read-command execution equivalence; admin project-scope preflight; explicit-key context-conflict precedence; project/experiment/inspection-context help behavior; help-schema; default/selected/top-level help availability; locked-preflight before handler argument effects; nested-help/preflight decision parity for handler payloads; generated explicit-credential, project-context, experiment-context, and inspection-context unavailable-command preflight rejection without handler parsing/file-read/output-write/DB/marker/token/filesystem side effects; global-public unsupported-option pre-side-effect behavior; all-registered-command unsupported-option runtime rejection without DB/config/marker/token side effects; generated all-registered-command trailing-global placement before handler errors without DB/config/marker/token side effects; generated zero-positional extra-argument runtime rejection without DB/config/marker/token/source/cache/export/worktree side effects; generated single-selector extra-argument and missing-required-selector runtime rejection without DB/config/marker/token/source/cache/export/worktree side effects; generated fixed-count positional extra-argument and missing-required-positional runtime rejection without config/source/secret/tag/audit side effects; command-local singleton option duplicate guarding with explicit repeated-option classification; generated registered command-local singleton duplicate-option runtime rejection without availability/selector/file-read/DB/config/marker/token side effects; generated registered-command success-field documentation coverage with English/Chinese synchronization, including alias handler inheritance; generated hard-remove force-confirm guard rejection without DB/config/marker/token/path side effects; generated dry-run-capable hard-remove preservation without DB/marker/token/path/trash side effects; generated actual hard-remove lifecycle-blocker rejection without DB/marker/token/path/trash side effects; generated actual hard-remove dependency-blocker rejection without DB/marker/token/path/project-tree/trash/source-ref side effects; generated mixed dry-run/force-confirm hard-remove rejection without DB/marker/token/path/project-tree/trash side effects; static mixed-mode guard coverage for future dry-run plus force-confirm handlers; docs-derived mixed-mode conflict declarations in both CLI specs; English/Chinese conflict-option equivalence; per-handler known-option structure; literal option-read allowlist coverage; English/Chinese docs-derived documented-option acceptance; English/Chinese documented-option equivalence; English/Chinese command-surface coverage against the registry; and selected English/Chinese success-field equivalence. They do not replace the broader generated golden matrix still needed for complete command-specific success/error rendering and no-side-effect behavior beyond saved baseline/env-secret/run/validation/submit result-failure output, unsupported-option, positional extra-argument rejection, explicit invalid-credential rejection, force-confirm guard rejection, command-local duplicate-option rejection, value-option missing-value rejection, typed value-parser malformed-value rejection, config/env/secret dry-run/skip-baseline conflict rejection, documented non-remove conflict rejection, dry-run hard-remove preservation, actual hard-remove lifecycle blockers, dependency blockers, and mixed remove-mode rejection.
- Broader package-index variability remains an opt-in environment concern outside the default suite.

Verification:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_local_runner_shell_mode_runs_through_sh tests/test_runner_local.py::test_project_config_schema_rejects_empty_runner_command_and_shell tests/test_runner_docker.py::test_docker_runner_shell_uses_container_sh -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_full_local_runner_strips_alab_credentials_and_internal_env_overrides tests/test_runner_docker.py::test_docker_runner_env_is_hostless_and_internal_env_overrides_config_env -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_local_runner_stdin_is_closed tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_local_runner_timeout_terminates_child_process_group -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_stdout_regex_reward_uses_redacted_and_truncated_stdout -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_local.py tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_local.py tests/test_runner_docker.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_skydiscover.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_skydiscover_python.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_skydiscover_python.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_env_secret_baseline_result_failures_follow_cli_spec tests/test_cli_contract.py::test_project_baseline_result_failures_follow_cli_spec tests/test_cli_contract.py::test_project_secret_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_env_success_fields_follow_cli_spec tests/test_smoke.py::test_project_secret_input_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_audit_secret_submission_and_tag_ddl_contract_checks_are_enforced tests/test_migrations.py::test_project_source_and_experiment_lifecycle_ddl_contract_checks_are_enforced -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_foundation_table_ddl_contract_checks_are_enforced tests/test_migrations.py::test_cache_entry_metadata_writers_use_safe_json_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_context_repair_accepts_ambient_admin_key tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_maintenance_prune_success_fields_follow_cli_spec tests/test_migrations.py::test_foundation_table_ddl_contract_checks_are_enforced -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts tests/test_cli_contract.py::test_maintenance_prune_success_fields_follow_cli_spec -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_source_remove_restores_deleted_ref_after_transaction_failure tests/test_smoke.py::test_experiment_remove_restores_branch_and_trash_after_transaction_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_source_remove_restores_deleted_ref_after_transaction_failure tests/test_smoke.py::test_experiment_remove_restores_branch_and_trash_after_transaction_failure tests/test_smoke.py::test_checkout_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_project_remove_restores_whole_tree_trash_after_transaction_failure tests/test_smoke.py::test_validation_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_observe_remove_restores_staged_trash_after_transaction_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_catalog.py -q`
- `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_catalog.py -q` (skips unless `git` and the live SkyDiscover remote are available)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py::test_networked_skydiscover_python_dependency_install -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_foundation_table_ddl_contract_checks_are_enforced tests/test_migrations.py::test_removed_path_registry_rows_do_not_block_path_reuse -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_project_source_and_experiment_lifecycle_ddl_contract_checks_are_enforced tests/test_migrations.py::test_required_storage_tables_and_columns_are_created -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced tests/test_migrations.py::test_run_records_allow_required_nullable_fields -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_secret_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_env_success_fields_follow_cli_spec tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_artifact_and_log_ddl_contract_checks_are_enforced tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced tests/test_migrations.py::test_required_storage_tables_and_columns_are_created -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_annotation_target_and_visibility_json_contracts tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_experiment_create_default_worktree_path_must_be_missing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_explicit_credentials_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_experiment_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_inspection_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_stop_global_prescan_at_standalone_separator_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_source_origin_metadata_contract_enforces_documented_shape tests/test_smoke.py::test_public_exp_create_inline_source_import -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_annotation_target_and_visibility_json_contracts tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_experiment_metadata_contract_enforces_documented_shape tests/test_cli_contract.py::test_experiment_create_source_ref_success_fields_follow_cli_spec tests/test_cli_contract.py::test_experiment_create_inline_source_variants_success_fields_follow_cli_spec tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_experiment_policy_json_contract_enforces_documented_shape tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_execution_record_json_contract_enforces_documented_shape tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_audit_json_contracts_enforce_documented_shape tests/test_cli_contract.py::test_audit_success_fields_follow_cli_spec tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_submission_refs_json_contract_enforces_documented_shape tests/test_cli_contract.py::test_submit_success_fields_follow_cli_spec tests/test_smoke.py::test_local_project_run_submit_workflow -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_project_config_json_contract_enforces_documented_shape tests/test_smoke.py::test_project_secret_input_contract tests/test_cli_contract.py::test_project_config_show_export_never_render_raw_secret_values -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_english_and_chinese_conflict_option_contracts_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_dry_run_force_confirm_remove_docs_declare_mixed_mode_conflict -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_context_token_file_permission_warning_renders_after_primary_result tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_cli_token_writes_use_private_permissions_and_git_exclude -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_known_options_are_duplicate_guarded_or_explicitly_repeatable tests/test_cli_contract.py::test_logs_show_rejects_duplicate_include_hidden_before_lookup -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_representative_singleton_duplicate_options_fail_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_singleton_options_reject_duplicates_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_value_options_reject_option_tokens_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_non_remove_documented_conflicts_fail_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_harbor_runner_separate_verifier_image tests/test_real_docker.py::test_real_harbor_runner_separate_verifier_tests_dockerfile -q` (skips unless `ALAB_RUN_REAL_DOCKER=1` and Docker/images are available)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_handlers_validate_positional_arguments -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_zero_positional_commands_reject_extra_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_single_selector_commands_reject_extra_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_required_single_selector_commands_reject_missing_selector_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_fixed_positional_commands_reject_extra_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_fixed_positional_commands_reject_missing_required_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_known_options_are_duplicate_guarded_or_explicitly_repeatable tests/test_cli_contract.py::test_known_option_allowlists_cover_literal_option_reads tests/test_cli_contract.py::test_literal_value_option_reads_are_registered_for_positional_parsing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_known_option_allowlists_cover_literal_option_reads tests/test_cli_contract.py::test_literal_value_option_reads_are_registered_for_positional_parsing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_have_success_field_contracts_in_cli_specs tests/test_cli_contract.py::test_registered_command_success_field_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_context_marker_json_contract_enforces_documented_shape tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_cli_contract.py::test_project_read_command_success_fields_follow_cli_spec -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_reject_unsupported_options_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_accept_trailing_globals_before_handler_errors_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_force_confirm_commands_reject_incomplete_confirmation_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_dry_runs_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_dry_run_force_confirm_remove_handlers_use_mixed_mode_guard -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_dry_run_force_confirm_remove_docs_declare_mixed_mode_conflict -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_registered_commands_reject_unsupported_options_without_side_effects tests/test_cli_contract.py::test_known_option_allowlists_cover_literal_option_reads tests/test_cli_contract.py::test_registered_command_handlers_gate_unknown_options -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_observe_lifecycle_aliases_render_canonical_shapes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_rfc3339_time_filters_require_explicit_offsets tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_smoke.py::test_project_secret_input_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Global Config Failure Gate Hardening

Implemented:

- Added a CLI entrypoint global-config gate so invalid persisted `config.toml` now blocks normal command and help execution with `CONFIG_INVALID`, while `auth init` and `config show|set|reset|validate` remain available for diagnosis or repair.
- Added explicit next-action rendering for unparseable global config TOML, directing users to `alab config reset --all`.
- Extended smoke coverage to prove unparseable global config prevents `config set`, field-level `config reset`, normal authenticated command execution, and no-command/`help`/`--help` rendering from rewriting or bypassing the broken file, while `config reset --all` restores defaults.
- Synchronized the English and Chinese CLI/test specs with the invalid-global-config gate and unparseable-TOML repair contract.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_global_repair_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_output_rich_is_single_command_and_non_persistent tests/test_cli_contract.py::test_default_help_runtime_hides_locked_commands_without_creating_home tests/test_cli_contract.py::test_global_public_commands_reject_unsupported_options_before_home_creation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Migration Lock Timeout Hardening

Implemented:

- Changed the home-level migration lock from indefinite blocking to nonblocking polling that honors `locks.acquire_timeout_ms` from the global config, falling back to the V1 default when the config is missing or unreadable.
- Added a `RESOURCE_BUSY` failure path with a safe retry next action when another process holds `.migration.lock` past the configured timeout.
- Added migration coverage proving a short configured timeout fails before opening or creating `alab.db`, while the existing default-timeout serialization behavior still waits for the lock and completes migration after release.
- Synchronized the English and Chinese test specs to require configured migration-lock timeout coverage.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_migration_lock_serializes_migrate_processes tests/test_migrations.py::test_migration_lock_timeout_uses_global_config -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/db.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 SQLite Busy Timeout Config Wiring

Implemented:

- Wired `storage.busy_timeout_ms` from global config into `Database.connect()` so ALab SQLite connections use the configured `PRAGMA busy_timeout` instead of a hard-coded value.
- Consolidated raw positive-integer global-config reads for early storage setup, sharing the fallback-safe path used by migration lock timeout configuration.
- Added storage tests proving the default busy timeout remains `5000` and a configured value is applied to new SQLite connections.
- Synchronized the English and Chinese CLI/storage/test specs to document `storage.busy_timeout_ms` as the SQLite busy-timeout control.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_database_connections_use_wal_mode tests/test_migrations.py::test_database_connections_use_configured_busy_timeout tests/test_migrations.py::test_migration_lock_timeout_uses_global_config -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/db.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Global Config Gate Ordering Hardening

Implemented:

- Split CLI request construction into a base request used for home/global-config gating and a hydrated request used for context detection plus explicit credential lookup.
- Ensured invalid global config is loaded and rejected before context or explicit credential lookup for non-repair commands, so a malformed `config.toml` cannot be masked by a bad `--key`.
- Preserved the existing help credential contract by only doing lightweight help-request detection before the gate; full help option parsing still runs after explicit credential validation when config is valid.
- Extended smoke coverage to prove a bad explicit key still yields `CONFIG_INVALID` when the global config TOML is broken, and synchronized the English and Chinese test specs.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_debug_stack_trace_only_for_internal_errors tests/test_cli_contract.py::test_debug_mode_traces_only_internal_system_failures -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation tests/test_cli_contract.py::test_key_stdin_input_validation_is_strict_global_contract tests/test_cli_contract.py::test_default_help_runtime_hides_locked_commands_without_creating_home tests/test_cli_contract.py::test_ambient_key_does_not_broaden_help_capability_display tests/test_cli_contract.py::test_explicit_root_key_help_capability_display_follows_registry_credentials tests/test_cli_contract.py::test_explicit_admin_key_help_capability_display_is_project_scoped -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py tests/test_smoke.py tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Real Docker Adapter Cache-Hit Hardening

Implemented:

- Extended the opt-in real Docker Harbor `tests/Dockerfile` verifier test so it runs the same Dockerfile-backed verifier twice and requires the second real container execution to reuse the ALab Docker image cache with `status = hit`.
- Extended the opt-in real Docker SkyDiscover Docker evaluator test so it records real Docker image-cache metadata and requires a second evaluator execution to hit the cache.
- Synchronized the English and Chinese test specs to include real Docker image-cache reuse for Dockerfile-backed adapter images in the full V1 opt-in Docker gate.

Validation:

- `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_harbor_runner_separate_verifier_tests_dockerfile tests/test_real_docker.py::test_real_skydiscover_docker_runner_evaluator -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Runner Status Text And Opt-In Test Docs Cleanup

Implemented:

- Removed stale adapter execution wording from `project init` now that Harbor and SkyDiscover project initialization resolves adapter-derived sources and participates in baseline validation.
- Replaced obsolete runner fallback messages that claimed non-local runners were not implemented in the milestone with precise unsupported-dispatch messages.
- Updated the English and Chinese README opt-in Docker test descriptions to mention real Docker image-cache reuse for Dockerfile-backed adapter images.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py src/alab/services.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py src/alab/services.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Python Opt-In Environment Revalidation

Validated:

- Re-ran the full opt-in real SkyDiscover Python dependency suite in the current environment with local-wheel, networked pure-Python, transitive dependency, and native/binary dependency paths enabled.
- Confirmed all four real-environment cases pass with the configured package index and `uv` environment cache, including cache-hit checks inside the tests.

Validation:

- `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest tests/test_real_skydiscover_python.py -q`

## 2026-05-21 README Opt-In Marker Contract

Implemented:

- Added a default-suite static contract that reads pytest markers from `pyproject.toml`, extracts `uv run pytest -m ...` opt-in commands from `README.md` and `README_cn.md`, and scans `tests/` for actual declared-marker usage.
- The contract now requires English README commands, Chinese README commands, declared pytest markers, and actual opt-in test markers to stay synchronized.
- Synchronized the English and Chinese test specs with this README/marker contract.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Host Support Policy Proof

Implemented:

- Added `tests/test_cli_contract.py::test_host_support_policy_and_opt_in_runner_gates_are_documented`.
- Proved the host policy row for current default/local scope by asserting the current host is macOS/Linux, blueprint and Chinese blueprint exclude Windows from V1 acceptance, README/README_cn document opt-in real runner commands, and `pyproject.toml` keeps the opt-in real runner markers.
- Kept real Docker/Harbor/SkyDiscover validation as `ENV-GATED`.

Validation:

- Focused host-policy checks are included in the post-batch docs/static validation run.

## 2026-05-21 Live SkyDiscover Catalog Revalidation

Validated:

- Re-ran the opt-in live SkyDiscover catalog test against the current environment and official remote.
- Confirmed the live path passes without skipping: catalog add/update clones and pins an exact commit, `catalog show` remains no-network, a real evaluator ref is discovered, and `project init skydiscover --source-empty --skip-baseline-test` resolves it.

Validation:

- `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_catalog.py -q`

## 2026-05-21 Markdown Chinese Pair Contract

Implemented:

- Added a default-suite static contract that scans repository-root and `docs/` Markdown files and requires every English Markdown source to have a synchronized `*_cn.md` pair.
- The same contract rejects orphan `*_cn.md` files without an English source, covering `README`, `AGENTS`, `CORE`, blueprint, subsystem specs, and progress documentation.
- Synchronized the English and Chinese test specs with this documentation pairing requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 README Repository Structure Contract

Implemented:

- Added a default-suite static contract that parses the `Repository Structure` tree from `README.md` and `README_cn.md`.
- The contract requires the English and Chinese README structure trees to stay byte-for-byte synchronized at the path level and verifies every listed repository path exists.
- Synchronized the English and Chinese test specs with this README structure-tree requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `git diff --check`

## 2026-05-21 Local-Only Gitignore Contract

Implemented:

- Added a default-suite static contract that requires `.gitignore` to keep local agent notes (`AGENTS.md`, `AGENTS_cn.md`, `CORE.md`, `CORE_cn.md`) ignored.
- The same contract requires real environment files (`.env`, `.env.*`) to remain ignored while preserving `!.env.example` so documented example configuration can stay trackable.
- Synchronized the English and Chinese test specs with this local-only/sensitive-file ignore requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_local_agent_notes_and_env_files_are_gitignored tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Empty Ambient Key Handling

Implemented:

- Changed root/admin actor lookup so an empty ambient `ALAB_KEY` is treated as absent instead of being passed to credential verification.
- This keeps commands that need credentials on the documented `AUTH_REQUIRED` path when users load `.env.example` without filling in a key.
- Added auth-level coverage for missing versus empty ambient `ALAB_KEY`, and synchronized the English and Chinese CLI/test specs.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py::test_empty_ambient_alab_key_is_treated_as_absent tests/test_auth.py::test_credential_verification_requires_scope_project_status_mode_and_path tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_auth.py tests/test_smoke.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/services.py tests/test_auth.py tests/test_smoke.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Environment Example Contract

Implemented:

- Added `.env.example` as the central tracked example for local ALab, uv, debug, and opt-in validation environment variables while keeping real `.env` files ignored.
- Updated the English and Chinese README setup sections and repository structure trees to point contributors at `.env.example`.
- Added a default-suite static contract that requires `.env.example` to exist, rejects duplicate entries, checks the required local/opt-in environment keys, and verifies all README environment assignments are documented in the example file.
- Synchronized the English and Chinese test specs and local agent notes with the new environment-example contract.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables tests/test_cli_contract.py::test_local_agent_notes_and_env_files_are_gitignored tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Empty Global Option Value Hardening

Implemented:

- Tightened CLI global pre-scan so `--home ""`, `--output ""`, and `--key ""` fail with `CONFIG_INVALID` instead of falling through to default home resolution, generic output validation, or no-explicit-key capability behavior.
- Extended both the representative value-option test and the generated registered-command global-option matrix to cover empty string values while preserving the existing missing-value and option-looking-token failures.
- Synchronized the English and Chinese CLI/test specs with the empty global option value rule.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_value_options_reject_option_tokens_without_side_effects tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation tests/test_cli_contract.py::test_key_stdin_input_validation_is_strict_global_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/cli.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Command-Local Structural Empty Value Hardening

Implemented:

- Added shared command-local value validation so structural values such as selectors, paths, file paths, choices, and numeric inputs reject empty strings with stable `CONFIG_INVALID` errors.
- Preserved direct user-text empty-string semantics for body, summary, feedback, message, reason, author labels, goal text, and query filters where field-specific validators allow empty text.
- Tightened capability project-id probing so `--project ""` cannot silently fall back to the current context during availability checks.
- Updated project init metadata overrides to treat `--goal ""` as an explicit empty goal override while non-empty enforcement continues to apply to project name and task fields.
- Expanded the representative value-option no-side-effect matrix to cover empty structural command-local values for exports, source import, experiment path/tag, token mode, annotation target, submit file input, and SkyDiscover catalog origin URL.
- Synchronized the English and Chinese CLI/test specs with the structural-vs-user-text empty value distinction.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_value_options_reject_option_tokens_without_side_effects tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py src/alab/services.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/cli.py src/alab/services.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Generated Structural Empty Value Matrix

Implemented:

- Upgraded the command-local structural empty-value contract from representative cases to a generated registered-command matrix.
- The matrix now exercises every registered command-local value option with an absent value, and every structural command-local value option with an empty string value, while skipping documented direct user-text fields whose empty-string semantics are intentionally preserved.
- Reused the existing no-side-effect snapshot harness so the generated empty-value checks prove no DB/config/marker/token/tree/export/worktree mutations occur before rejection.
- Added a static guard that the direct-user-text empty-value allowlist remains inside the central value-option table.
- Synchronized the English and Chinese test specs with the generated structural empty-value requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Unsupported Option Side-Effect Matrix Hardening

Implemented:

- Strengthened the generated unsupported command-local option matrix so every registered non-help command now takes a fresh SQLite snapshot, config/marker/token file snapshot, and project/source/tmp/worktree tree snapshot before its unsupported-option invocation.
- The matrix now proves unsupported options leave those snapshots unchanged per command, rather than only checking aggregate state after the loop.
- Synchronized the English and Chinese test specs with the generated unsupported-option no-side-effect requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_reject_unsupported_options_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Global Pre-Scan Matrix Side-Effect Hardening

Implemented:

- Strengthened the generated trailing-global placement matrix so every registered non-help command now takes a fresh SQLite snapshot, config/marker/token file snapshot, and project/source/tmp/worktree tree snapshot before proving trailing `--home`, `--key`, and `--output text` are consumed by global pre-scan before handler validation.
- Strengthened the generated standalone-`--` matrix with the same per-command snapshots, proving global-looking tokens after `--` do not read `--key-stdin`, do not switch homes, and leave DB/config/marker/token/tree/worktree state unchanged.
- Synchronized the English and Chinese test specs with the stronger global pre-scan no-side-effect requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_accept_trailing_globals_before_handler_errors_without_side_effects tests/test_cli_contract.py::test_registered_commands_stop_global_prescan_at_standalone_separator_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Capability Preflight Matrix Side-Effect Hardening

Implemented:

- Strengthened the invalid explicit credential matrix so every registered command under `--key` and `--key-stdin` invalid credentials now takes a fresh SQLite snapshot, config/context file snapshot, and project/source/tmp tree snapshot before proving `AUTH_DENIED` short-circuits ahead of handler payload parsing.
- Strengthened project, experiment, and inspection unavailable-command preflight matrices so every command/payload pair now records fresh DB/file/tree snapshots before invoking the command.
- Expanded the experiment and inspection token-context tree snapshots to include `sources`, plus the active worktree or inspection checkout, so command-unavailable preflight checks prove no hidden staging occurs outside the immediate output path.
- Added explicit failure diagnostics for DB, watched-file, and watched-tree preservation in these matrices.
- Synchronized the English and Chinese test specs with the fresh per-command/per-payload preflight snapshot requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_project_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_experiment_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_inspection_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Positional Matrix Side-Effect Hardening

Implemented:

- Strengthened the generated zero-positional, single-selector, required-selector, fixed-count extra, and fixed-count missing positional matrices so every registered-command case now takes a fresh SQLite snapshot, watched config/context/token file snapshot, and project/source/tmp/worktree tree snapshot before invocation.
- Added per-command diagnostics for DB, watched-file, watched-tree, export, checkout, and worktree preservation when positional validation fails before handler side effects.
- Upgraded the annotation target-id preflight matrix to the same fresh per-case snapshot pattern after the broader positional edit surfaced an old aggregate-snapshot assumption.
- Synchronized the English and Chinese test specs with the fresh per-command positional snapshot requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_zero_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_single_selector_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_required_single_selector_commands_reject_missing_selector_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_missing_required_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads tests/test_cli_contract.py::test_zero_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_single_selector_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_required_single_selector_commands_reject_missing_selector_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_missing_required_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Hard Remove Matrix Side-Effect Hardening

Implemented:

- Strengthened the hard-remove confirmation matrix so every command and missing-force, missing-confirm, and wrong-confirm variant now takes fresh SQLite, watched-file, tree, and trash snapshots before invocation.
- Strengthened hard-remove dry-run coverage so every remove command proves dry-run output leaves DB rows, context/token files, project/source/workspace/worktree trees, inspection checkouts, and trash state unchanged per command.
- Strengthened mixed `--dry-run` plus `--force/--confirm` conflict coverage with the same fresh per-command/variant snapshots.
- Strengthened lifecycle and dependency blocker matrices with fresh per-command snapshots, including source Git ref checks for dependency blockers.
- Added a tree snapshot helper that preserves root existence as well as contents, so empty trash directory creation or removal is observable.
- Synchronized the English and Chinese test specs with the per-command hard-remove snapshot requirements.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_force_confirm_commands_reject_incomplete_confirmation_without_side_effects tests/test_cli_contract.py::test_hard_remove_dry_runs_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Explicit Credential Surface Preflight Snapshot Hardening

Implemented:

- Strengthened the explicit root/admin credential-surface preflight matrix so token-only commands under root credentials and root/token commands under admin credentials now take fresh DB/file/tree snapshots for every command/payload pair.
- The matrix now reports DB, watched-file, watched-tree, touched-path, and touched-parent preservation failures directly.
- Isolated `--key-stdin` variants through a per-invocation monkeypatch context.
- Synchronized the English and Chinese test specs with the fresh per-command/payload snapshot requirement for explicit credential surfaces.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_explicit_credentials_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Command Option Matrix Snapshot Hardening

Implemented:

- Strengthened the registered singleton duplicate-option matrix so every command/option case now takes fresh DB, watched-file, watched-tree, export-path, and worktree-path snapshots before invocation.
- Strengthened the registered missing-value and structural-empty value-option matrix with fresh per-command/option snapshots for both absent-value and empty-string cases.
- Strengthened the typed/structured malformed value matrix with fresh per-command/option/value snapshots across pagination, limits, choices, object ids, hashes, RFC 3339 timestamps, and selector filters.
- Strengthened project config/env/secret dry-run/skip-baseline conflict coverage and documented non-remove conflict coverage with fresh per-case snapshots.
- Synchronized the English and Chinese test specs with the fresh per-case command-option and conflict snapshot requirements.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_singleton_options_reject_duplicates_without_side_effects tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads tests/test_cli_contract.py::test_non_remove_documented_conflicts_fail_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Real Dockerfile Runner Coverage

Implemented:

- Added an opt-in real Docker test for the plain Docker runner's Dockerfile path, separate from image-based Docker runner coverage.
- The test builds a real Dockerfile runner image from a generated build context, verifies `.dockerignore` excludes an ignored file from the image context, verifies the mounted ALab workspace/run directory contract, and checks the parsed reward.
- The same config is run twice and asserts the second run hits ALab's Docker image cache with the same cache key and Docker tag.
- Synchronized the English and Chinese test specs so real Docker coverage explicitly includes Dockerfile runner build context and cache reuse.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_runner_dockerfile_build_context_and_cache -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 README Real Docker Coverage Sync

Implemented:

- Updated README and README_cn opt-in Docker validation guidance so it explicitly mentions Docker image and Dockerfile runners, Dockerfile build-context filtering, and Dockerfile runner cache reuse in addition to Harbor/SkyDiscover Docker coverage.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `git diff --check`

## 2026-05-21 Real Docker Shell Mode Coverage

Implemented:

- Added an opt-in real Docker shell-mode runner test to complement the existing fake-Docker shell argv contract.
- The test runs an Alpine container through `runner.shell`, verifies `/bin/sh -c` can see ALab's container workspace/run-dir environment, writes a run-dir file from inside the shell, and parses a stdout reward.
- Synchronized README, README_cn, and the English/Chinese test specs so real Docker coverage explicitly includes Docker image command and shell execution.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_runner_shell_mode_uses_container_sh -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Real Docker Environment Isolation Coverage

Implemented:

- Added an opt-in real Docker environment-boundary test for the Docker image runner.
- Extended the default fake-Docker environment contract test and the opt-in real Docker test to cover the full internal operation env set.
- The tests prove Docker runners do not inherit host-only environment variables or host `ALAB_*` credentials, while internal ALab operation variables override conflicting `[env]` values.
- The same tests verify explicit project/experiment/run/config-version/workspace/run-dir injection, user-visible non-secret env injection, secret env injection, reward parsing, and secret non-rendering in captured stdout.
- Synchronized README and README_cn opt-in Docker guidance with the internal `ALAB_*` override precedence covered by the real Docker gate.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_runner_env_is_hostless_and_internal_env_wins tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_runner_env_is_hostless_and_internal_env_overrides_config_env -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_local.py tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py tests/test_runner_docker.py tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py tests/test_runner_local.py tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py tests/test_runner_docker.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Python Environment Boundary Coverage

Implemented:

- Added default-suite SkyDiscover Python evaluator-wrapper coverage for the V1 runner environment boundary.
- The test proves host-only environment variables and host `ALAB_*` credentials are stripped, internal ALab operation variables override conflicting `[env]` values, and evaluator-visible `ALAB_WORKSPACE`/`ALAB_RUN_DIR` point at the local runner workspace/run directory.
- The same test verifies user env injection, secret env injection, hidden evaluator stdout capture, and exact secret redaction in hidden stdout.
- Synchronized the English and Chinese test specs with the SkyDiscover Python environment-boundary coverage requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_python_runner_env_boundary_and_redaction tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Docker Environment Boundary Coverage

Implemented:

- Extended the default fake-Docker SkyDiscover Docker evaluator test so it now covers the full Docker-backed runner environment boundary.
- The test now proves the evaluator run receives the hidden bundle mount, workspace/program/run-dir container paths, explicit project/experiment/run/config-version env, user env, and secret env while host-only variables and host `ALAB_*` credentials stay out of the Docker `--env` set.
- It also verifies internal adapter env values such as `ALAB_PROGRAM_PATH` override conflicting `[env]` values and that hidden evaluator stderr redacts secret values.
- Synchronized the English and Chinese test specs with the SkyDiscover Docker environment-boundary coverage requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_docker_runner_builds_hidden_bundle_and_parses_metrics tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `git diff --check`

## 2026-05-21 Harbor Shared Verifier Environment Boundary Coverage

Implemented:

- Extended the default fake-Docker Harbor shared-verifier test to cover the full Docker-backed runner environment boundary.
- The test now verifies host-only variables and host `ALAB_*` credentials are excluded from Docker `--env`, internal ALab operation variables and `ALAB_HARBOR_TASK_DIR` override conflicting `[env]` values, and Harbor task env plus external secret env values are both injected.
- It also verifies hidden verifier logs redact both Harbor task literal env secrets and caller-provided secret env values.
- Synchronized the English and Chinese test specs with the Harbor fake-Docker environment-boundary coverage requirement.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py::test_harbor_shared_verifier_runs_with_hidden_logs_and_secret_redaction tests/test_runner_harbor.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_harbor.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_harbor.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Python Sandbox Summary Coverage

Implemented:

- Added a stable `sandbox` field to root/admin project summaries and project config summaries.
- SkyDiscover Python configs now render `sandbox: not-os-sandbox`; other runner types render `sandbox: not-declared`, keeping output shapes stable while making the Python evaluator's non-OS-sandbox boundary explicit.
- Extended SkyDiscover Python smoke coverage to assert both `project show` and `project config show` render the non-OS-sandbox summary.
- Synchronized the English and Chinese CLI specs with the new `sandbox` field and rule.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_cli_contract.py::test_project_read_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_config_show_export_never_render_raw_secret_values -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_registered_commands_have_success_field_contracts_in_cli_specs tests/test_cli_contract.py::test_project_read_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_config_show_export_never_render_raw_secret_values tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/services.py tests/test_smoke.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Visible Output Hidden-Asset Guard Coverage

Implemented:

- Strengthened default SkyDiscover Docker and Python runner tests so visible stdout is explicitly checked for hidden-asset and path non-disclosure.
- The Docker evaluator test now proves visible output omits evaluator source paths, hidden bundle paths, hidden test data, and private evaluator stderr text while hidden logs still capture evaluator output.
- The Python evaluator test now proves visible output omits evaluator source paths, staging paths, evaluator file names, and private evaluator stdout while hidden logs still capture evaluator output.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py`
- `git diff --check`

## 2026-05-21 Docker Setup Output Hidden-Log Coverage

Implemented:

- Generic Docker runner setup output from image pull/build/inspect is now retained in `hidden_stdout`/`hidden_stderr`, redacted with configured secret bytes, and kept out of user-visible runner stdout/stderr.
- Docker setup failures now return stable visible failure reasons such as `docker build failed` while preserving raw setup diagnostics only in hidden logs.
- Added default fake-Docker coverage for hidden setup output, hidden validation-log persistence, redaction, `DOCKER_SETUP_OUTPUT_CAPTURED`, image auto-pull, Docker default-network argument shape, and Dockerfile cache keys ignoring run-time fields while changing for build inputs.
- Fixed the opt-in real Docker test assertion to use the current `warning_codes` result field.
- Synchronized the English and Chinese runner/test specs with the hidden setup-output behavior.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_project_init_persists_docker_setup_output_as_hidden_validation_logs tests/test_runner_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py tests/test_runner_docker.py tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py tests/test_runner_docker.py tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Real Adapter Docker Environment Boundary Coverage

Implemented:

- Extended the opt-in real Docker Harbor shared-verifier test so the real verifier container now checks host-only variables and host `ALAB_*` credentials are absent, internal ALab operation variables override conflicting `[env]` values, and both Harbor task env and caller secret env values are injected.
- The same Harbor path now emits task and caller secret values from inside the real container and verifies hidden verifier logs redact both exact bytes.
- Extended the opt-in real SkyDiscover Docker evaluator test so the real evaluator container now checks hostless env behavior, internal `ALAB_*` and `ALAB_PROGRAM_PATH` override precedence, user env injection, and secret env injection across both initial and cache-hit executions.
- The SkyDiscover Docker real-container path now emits the secret on evaluator stderr and verifies visible summaries omit it while hidden stderr stores only the redacted value.
- Updated README/README_cn and the English/Chinese test specs so opt-in Docker validation explicitly covers these adapter environment-boundary checks.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Same-Parent Trash Fallback Integration Coverage

Implemented:

- Added CLI-level worktree remove coverage for cross-device trash staging fallback.
- The test now simulates an `EXDEV` failure when moving an experiment worktree into ALab home trash, exercises the real `exp worktree remove --force --confirm` path, and verifies ALab falls back to `.alab-trash-<audit_id>` in the target's parent directory.
- The same coverage proves output and audit metadata record `same_parent` trash mode with a sanitized label, immediate cleanup removes the same-parent trash directory, no active trash cache row remains, and the experiment row is marked removed.
- This complements the lower-level helper test and closes the previous "same-parent fallback lacks filesystem-level integration coverage" gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_uses_same_parent_trash_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_uses_same_parent_trash_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Interrupted Record Observe Coverage

Implemented:

- Strengthened stale running record coverage beyond DB mutation checks.
- The smoke test now uses real complete run/validation ids, interrupts a stale running run and validation through `status`, and verifies the interrupted run is visible through token-scoped `runs list --status interrupted`, absent from `--status running`, searchable by failure reason, and stable through `runs show`.
- The same coverage verifies interrupted runs render nullable fields correctly in CLI output, including `exit code: none`, `reward: none`, `reward parse status: not_attempted`, non-null `ended at`, and `hidden log available: false`.
- It also verifies the interrupted validation is no longer treated as a running blocker by successfully archiving it through the project validation lifecycle path.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Experiment Operation Lock Submit Expiry Coverage

Implemented:

- Strengthened the experiment operation-lock smoke coverage so the shared run/submit lock path now proves expired locks are replaced for both `run` and `submit`.
- The test now covers an active lock blocking `submit` without writing a submission, then replaces an expired lock and verifies the final submission succeeds.
- Added a reusable successful-submission field-label helper and switched existing success assertions to use it, keeping the submit output contract checks consistent with the failure helper.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Oversized Artifact Skip Workflow Coverage

Implemented:

- Added CLI-level smoke coverage for oversized artifact capture across baseline validation and experiment runs.
- The test now verifies oversized artifacts are persisted as `status = skipped` with size metadata and no content hash, while both the validation and run still pass.
- The same coverage verifies skipped artifacts are visible through `artifacts list --status skipped`, absent from `--status captured`, and cannot be exported because no blob bytes were captured.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Artifact Symlink Escape Workflow Coverage

Implemented:

- Added CLI-level smoke coverage for artifact symlinks whose resolved targets escape the configured artifact root.
- The test now verifies escaping run-dir symlinks are persisted as `status = skipped` with no size or content hash, while baseline validation and experiment runs still pass.
- The same coverage verifies skipped symlink artifacts are absent from captured-artifact listings and cannot be exported because ALab did not capture target bytes outside the artifact root.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Non-Passed Run Artifact Capture Workflow Coverage

Implemented:

- Added CLI-level smoke coverage proving available run artifacts are still captured for non-passed run outcomes.
- The test now covers runner failure, reward parse error, and timeout paths, each writing a run artifact before the non-passed outcome is recorded.
- The same coverage verifies each run renders `artifact count: 1`, each captured artifact is visible through `artifacts list --status captured`, and exported bytes exactly match the produced artifact content.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Archived Hidden Log Lifecycle Coverage

Implemented:

- Strengthened the Harbor hidden-log smoke workflow to cover archived hidden logs, not only active hidden logs.
- The test now verifies root/admin `logs show --include-hidden` can inspect an archived hidden log safely, while `logs list --include-hidden` still hides it unless `--include-archived` is also provided.
- The same coverage verifies hidden archived log export fails without `--include-archived`, succeeds with both `--include-hidden` and `--include-archived`, preserves redaction, and keeps token archive/unarchive/remove denials intact.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_config_source_observe_and_tags tests/test_runner_harbor.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 File Reward Limit Saved-Failure Coverage

Implemented:

- Added CLI-level smoke coverage for the rule that file reward parsing reuses `artifacts.per_file_limit_bytes`.
- The test now verifies an oversized file reward is stored as a saved baseline validation failure with `reward_parse_status = invalid`, `reward.value = null`, and a stable failure reason.
- The same coverage verifies the valid-baseline experiment path records an oversized file reward as a saved run error with `REWARD_PARSE_ERROR`, persists the same reward/failure metadata, and remains discoverable through `runs list --failure-reason-query`.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_local.py::test_file_reward_rejects_symlink_escape_at_parse_time tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Missing Working Directory Saved-Failure Coverage

Implemented:

- Added CLI-level smoke coverage for source-dependent `runner.working_directory` paths that are schema-valid but missing in the selected source snapshot.
- The test now verifies a missing working directory is saved as a baseline validation `error` with `reward_parse_status = not_attempted`, stderr preview text, and stable failure metadata instead of being rejected as a config-shape error.
- The same coverage verifies a valid baseline can later produce a saved run `RUNNER_ERROR` when the experiment source removes the configured working directory, and that the run remains discoverable by failure-reason filtering.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_runner_local.py::test_project_config_rejects_working_directory_with_sibling_prefix tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_local.py::test_file_reward_rejects_symlink_escape_at_parse_time -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Missing File Reward Saved-Failure Coverage

Implemented:

- Added CLI-level smoke coverage for configured `reward.path` values that are schema-valid but missing in the selected source/run output snapshot.
- The test now verifies a missing baseline reward file is saved as a validation `error` with `reward_parse_status = invalid`, `reward.value = null`, and stable failure metadata.
- The same coverage verifies a valid baseline can later produce a saved run `REWARD_PARSE_ERROR` when the experiment no longer writes the configured reward file.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_local.py::test_file_reward_rejects_symlink_escape_at_parse_time tests/test_runner_local.py::test_project_config_rejects_working_directory_with_sibling_prefix -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Primary Metric Failure Coverage

Implemented:

- Added runner-level coverage for SkyDiscover Python reward parsing when `combined_score` is absent.
- The new runner test verifies the default SkyDiscover primary-metric path falls back to averaging finite numeric top-level metrics, while a custom configured primary metric that is missing produces `status = error`, `reward_parse_status = missing`, and a stable missing-metric failure reason.
- Added CLI-level smoke coverage proving a missing custom SkyDiscover primary metric is saved as a baseline validation failure with persisted metrics, `reward.value = null`, visible safe metric names, and stable failure metadata.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_python_reward_fallback_and_missing_custom_primary_metric tests/test_smoke.py::test_skydiscover_python_missing_primary_metric_is_saved_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_missing_primary_metric_is_saved_failure tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_skydiscover.py`
- `git diff --check`

## 2026-05-21 Stdout Regex Truncation Saved-Failure Coverage

Implemented:

- Added CLI-level smoke coverage for `stdout_regex` rewards that read redacted, truncated stdout.
- The test now verifies a baseline validation whose reward text is beyond `logs.stdout_limit_bytes` is saved as an invalid project with `reward_parse_status = missing`, `reward.value = null`, a stable missing-reward failure reason, and a truncated stdout log record.
- The same coverage verifies a valid-baseline experiment can later produce a saved run `REWARD_PARSE_ERROR` when the reward text moves beyond the stored stdout limit, preserving the truncated preview and remaining discoverable through `runs list --failure-reason-query`.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure tests/test_runner_local.py::test_stdout_regex_reward_uses_redacted_and_truncated_stdout tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Missing Dockerfile/Context Saved-Failure Coverage

Implemented:

- Added CLI-level Docker runner coverage for source-dependent Dockerfile and build-context paths that are schema-valid but absent from the selected source snapshot.
- The new test verifies a missing baseline `runner.dockerfile` is saved as an invalid project validation with `status = error`, `reward_parse_status = not_attempted`, a stable runner failure reason, and a persisted stderr log record.
- The same coverage verifies a valid-baseline experiment can later remove the configured Docker build context and produce a saved run `RUNNER_ERROR` without requiring real Docker for the missing-path failure.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error tests/test_runner_docker.py::test_docker_config_paths_must_stay_inside_workspace tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py`
- `git diff --check`

## 2026-05-21 Nonzero Reward-Parse Failure Coverage

Implemented:

- Strengthened non-passed run artifact coverage with the reward-status edge case where the runner exits non-zero and reward parsing also fails.
- The test now verifies this path stays `run status = failed`, records `reward_parse_status = invalid`, keeps the user-facing failure as `RUNNER_FAILED` with the original exit code, and still persists `reward.value = null` in `record_json`.
- The same workflow continues to prove best-effort artifact capture runs for failed, reward-parse-error, and timed-out runs when runtime directories remain available.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Artifact Directory Glob CLI Coverage

Implemented:

- Added CLI-level smoke coverage for artifact directory glob expansion, unprefixed workspace-root glob capture, stable path sorting, and duplicate suppression across overlapping artifact globs.
- The test now verifies baseline validation artifacts created from explicit file globs plus a containing directory glob produce one captured row per file, not duplicate rows, and render in normalized path order when sorted by path.
- The same coverage verifies run artifacts from the same glob shape persist captured rows for both `run` and default `workspace` roots, report the correct artifact count, and export exact captured bytes.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_directory_globs_expand_sort_deduplicate_and_export -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_directory_globs_expand_sort_deduplicate_and_export tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Log Redaction Before Truncation Coverage

Implemented:

- Added CLI-level smoke coverage proving secret redaction happens before stdout/stderr truncation and storage.
- The test uses a log byte limit that would leak a partial secret if truncation happened first, then verifies baseline validation stdout/stderr logs store `prefix [REDACTED]`, mark `truncated = true`, and contain no raw or partial secret text.
- The same coverage verifies saved run previews and run log records preserve the same redacted-then-truncated behavior, and that log `stored_bytes`, `content_hash`, and exported byte files match the exact stored redacted prefix.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Global Preview Bytes Log Coverage

Implemented:

- Wired `output.preview_bytes` into validation and experiment run log storage so saved stdout/stderr previews no longer use a hard-coded 4096-byte prefix.
- The same preview limit now applies consistently to visible and hidden log streams created by the validation and run capture paths.
- Added CLI-level smoke coverage proving a non-default global preview length is reflected in baseline validation log list output, saved experiment run previews, run log list output, and persisted `log_streams.preview_text` metadata without truncating the stored log bytes.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_preview_bytes_controls_validation_and_run_log_previews -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_global_preview_bytes_controls_validation_and_run_log_previews tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py src/alab/services.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py src/alab/services.py tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Logs Show Full Content Coverage

Implemented:

- Split `observe logs show` rendering from lightweight log list/export metadata so `show` now reads the stored log byte file and renders safe UTF-8 replacement-decoded full log `content`.
- Preserved the existing `logs list` and `logs export` field shapes while documenting `logs show` as the full-content CLI surface promised by the runner spec.
- Extended smoke and CLI-contract coverage so active visible logs, archived visible logs, hidden logs shown by root/admin with `--include-hidden`, and top-level `logs show` aliases all render the documented `content` field without exposing redacted hidden-log secrets.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_cli_contract.py::test_observe_read_aliases_render_equivalent_outputs tests/test_cli_contract.py::test_observe_lifecycle_aliases_render_canonical_shapes -q`

## 2026-05-21 Progress Dashboard Consolidation

Implemented:

- Added a top-level current snapshot so future readers can see the actual V1 implementation state without reading the full dated journal.
- Added an authoritative active backlog split into P0 completion blockers, P1 release hardening, and P2 maintenance, making older historical `Known incomplete areas` explicitly non-authoritative unless promoted into the active backlog.
- Added next-best-batch guidance and progress-file maintenance rules so future updates keep the dashboard current while preserving the detailed implementation log as evidence.

Validation:

- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_registered_command_success_field_contracts_are_synchronized tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`

## 2026-05-21 Empty Ambient Credential Contract Coverage

Implemented:

- Added focused CLI-contract coverage for the `ALAB_KEY=""` ambient environment case required by `docs/spec_tests.md`.
- The test proves an empty ambient key behaves exactly like an absent credential for project-context repair: `AUTH_REQUIRED`, exit `3`, stable error rendering, matching absent-key stderr, and no SQLite side effects.
- Updated the progress dashboard's recent-batch and next-batch summaries so the top of this file continues to show the actionable current state.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_empty_ambient_alab_key_behaves_like_absent_credential tests/test_cli_contract.py::test_key_stdin_input_validation_is_strict_global_contract tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Completion Audit Evidence Matrix

Implemented:

- Added `docs/completion_audit.md` as the active V1 requirement-to-evidence ledger, separate from this chronological progress log.
- Added synchronized `docs/completion_audit_cn.md` so the new audit artifact follows the project's English-first plus Chinese-pair documentation rule.
- Seeded the matrix with P0 completion gates and grouped evidence rows for CLI contracts, storage/auth/context, project/source/experiment/observe collaboration, and runner/adapter coverage.
- Explicitly marked remaining proof work as `PARTIAL`, `PENDING`, or `ENV-GATED` instead of treating grouped evidence as completion proof.
- Updated the progress dashboard so the audit ledger is now the next P0 entry point.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Observe Unarchive Idempotency Coverage

Implemented:

- Strengthened lifecycle smoke coverage for run, artifact, and log unarchive idempotency.
- Repeated unarchive now verifies stable field labels, unchanged `unarchived at` timestamps, `audit id: none`, and no duplicate unarchive audit rows.
- Re-archives the objects after idempotency checks so the existing hard-remove and reference-counted trash coverage continues through the archived path.
- Updated `docs/completion_audit.md` and `docs/completion_audit_cn.md` to record the stronger evidence while keeping the lifecycle row `PARTIAL` until every lifecycle command is audited row by row.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Lifecycle Evidence Row Audit

Implemented:

- Expanded the lifecycle section of `docs/completion_audit.md` into a per-object evidence table for project, source, validation, experiment, run, artifact, log, annotation, worktree, and inspection checkout lifecycle surfaces.
- Mapped archive/unarchive idempotency evidence separately from remove/dry-run/blocker evidence so future audit work can see which tests prove which lifecycle rule.
- Kept the grouped lifecycle row marked `PARTIAL` until the full default suite is rerun and the broader requirement-level audit is complete, while marking each object-family row as proved pending that full-suite rerun.
- Updated `docs/completion_audit_cn.md` with the synchronized Chinese evidence mapping.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_dry_runs_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Default Suite Verification

Implemented:

- Ran the full default pytest suite after the lifecycle/audit consolidation batch; default opt-in real-environment tests skipped as expected under their markers.
- Ran repository-wide `ruff`, `compileall`, and whitespace checks after the full pytest run.
- Updated `docs/completion_audit.md` and `docs/completion_audit_cn.md` so the default-suite P0 gate records the passed command set while still requiring reruns after future changes.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Project Source Experiment Audit Expansion

Implemented:

- Expanded `docs/completion_audit.md` with requirement-level evidence rows for the highest-risk parts of `docs/spec_project_source_experiment.md`.
- Added rows for project config schema, runtime baseline/config edit semantics, config read/export secret-retain behavior, project init precedence, source import/model behavior, public inline source import, experiment creation/visibility/mutable scope, and run/submit lifecycle.
- Marked rows as `PROVED` only when current default-suite evidence is direct enough; kept broader rows `PARTIAL` where the remaining work is row-level mapping or a specific missing evidence check.
- Updated `docs/completion_audit_cn.md` with the synchronized Chinese audit expansion.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Storage Auth Context Audit Expansion

Implemented:

- Expanded `docs/completion_audit.md` with requirement-level evidence rows for the highest-risk parts of `docs/spec_storage_auth_context.md`.
- Added rows for home/init behavior, SQLite connection and DDL contracts, migration and backup policy, canonical JSON shapes, credential/token behavior, secret handling, global config, context marker/path registry behavior, capability resolver preflight, context repair, locks/stale cleanup, and audit retention/sanitization.
- Marked direct default-suite evidence as `PROVED` only where it is already assertion-level; left broader areas `PARTIAL` with concrete remaining audit tasks such as home-id entropy evidence, old-experiment secret binding, conflicted-marker variants, inspection self-repair pinned-commit checks, and per-object audit metadata review.
- Updated `docs/completion_audit_cn.md` with the synchronized Chinese audit expansion.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Observe Collaboration Audit Expansion

Implemented:

- Expanded `docs/completion_audit.md` with requirement-level evidence rows for `docs/spec_observe_collaboration.md`.
- Added rows for visibility policy and token/inspection intersection, observe command and alias surfaces, search corpus privacy, pagination/filter/sort contracts, best ranking, run/log access, artifact export, tags, annotation targets and revisions, and public safe status.
- Kept broad rows `PARTIAL` where current tests are strong but not exhaustive, with concrete remaining actions such as regenerated-token visibility matrices, every sort whitelist, `best` tie ordering, hidden-log archived export branches, hidden-asset artifact exclusion, annotation dirty-worktree variants, and public safe-status negative fields.
- Updated `docs/completion_audit_cn.md` with the synchronized Chinese audit expansion.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Runner Adapter Audit Expansion

Implemented:

- Expanded `docs/completion_audit.md` with requirement-level evidence rows for `docs/spec_runners_adapters.md`.
- Added rows for shared runner contracts, config path/schema validation, local runner behavior, Docker runner/cache/capability behavior, reward extraction, artifact capture, logs/hidden logs, Harbor adapter contracts, SkyDiscover catalog/source/evaluator behavior, and real-environment validation gates.
- Separated default fake/local proof from `ENV-GATED` real Docker, live SkyDiscover catalog, network dependency, and native dependency validation so future completion claims cannot overstate fake-adapter evidence.
- Updated `docs/completion_audit_cn.md` with the synchronized Chinese audit expansion.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 CLI Long Tail Audit Expansion

Implemented:

- Expanded `docs/completion_audit.md` with a dedicated CLI long-tail evidence table drawn from `docs/spec_cli.md` and the golden CLI section of `docs/spec_tests.md`.
- Split the remaining CLI work into parser, positional selector, renderer, success-schema, saved result-failure, system-error/debug, error/warning matrix, capability preflight, file-payload, and repository documentation contract rows.
- Marked parser and renderer foundations as `PROVED` where generated/current tests are direct, and kept rows `PARTIAL` where exact remaining work is known: Git SHA selector abbreviation/ambiguity, conditional alias success variants, saved failure breadth, exhaustive error matrices, capability payload variants, and invalid file-payload cases.
- Updated the progress dashboard so the remaining P0 backlog now points to blueprint-level product invariants and specific `PARTIAL` rows rather than a generic "CLI long-tail" bucket.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Blueprint Product Invariants Audit Expansion

Implemented:

- Expanded `docs/completion_audit.md` with a blueprint-level product invariants table so the completion ledger now covers `docs/blueprint.md` directly instead of only subsystem specs.
- Added rows for local-only product scope, core workflow, object model, plaintext/security boundaries, runtime stack and architecture, ALab home layout, CLI/output contract, source/public experiment direction, lifecycle direction, runner/adapter direction, documentation discipline, and host/release gates.
- Kept absence-of-feature and release-environment-dependent rows `PARTIAL` or `ENV-GATED` rather than overstating proof from broad implementation shape.
- Updated the progress dashboard so the next work is now converting high-risk `PARTIAL` rows into tests or exact evidence references.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Runtime Surface Contract Guard

Implemented:

- Added `tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies`.
- The test reads `pyproject.toml` runtime dependencies and parses `src/alab/*.py` imports to reject banned server/web UI frameworks, ORMs, scheduler/agent-loop packages, and LLM-provider SDKs that are explicitly outside the V1 blueprint.
- Updated `docs/completion_audit.md` and `docs/completion_audit_cn.md` so the blueprint product-scope and runtime-stack rows cite this new absence-of-feature guard.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`

## 2026-05-21 ALab Home Layout Contract Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint`.
- The test covers default `~/.ALab` resolution under `HOME`, `ALAB_HOME`, explicit `--home` precedence, canonical home directories, no `records/` directory, database `home_id` persistence, project marker `home_id`, marker-only project control contexts, and cwd-relative default experiment worktree marker propagation.
- Fixed project initialization to create canonical `projects/<project_id>/artifacts/blobs` and `projects/<project_id>/artifacts/logs` directories immediately through `src/alab/services.py::_ensure_project_artifact_layout`, matching the blueprint layout before any artifact/log capture occurs.
- Updated the completion audit home/layout rows in English and Chinese with the new focused evidence.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_cli_contract.py`

## 2026-05-21 Progress Dashboard Log Split

Implemented:

- Split the current progress dashboard from the historical implementation journal. `docs/progress.md` is now a short current-status/backlog/next-batch dashboard, while `docs/progress_log.md` contains the full dated implementation journal.
- Added synchronized `docs/progress_log_cn.md` and reduced `docs/progress_cn.md` to the matching dashboard shape.
- Updated README, completion audit, and local AGENTS guidance so future agents read the short dashboard first and use the log only for historical evidence.
- Marked the full default-suite completion gate as stale for the current worktree because implementation and documentation changes landed after the last full-suite pass.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `git diff --check`

## 2026-05-21 Experiment-Bound Secret Coverage

Implemented:

- Added `tests/test_smoke.py::test_experiment_runs_keep_bound_secret_after_project_secret_change`.
- The test creates an experiment under config version 1 with an initial `secret_env` value, changes the project secret to create a new active config version, then proves the existing experiment still runs with config version 1 and the original secret while a newly created experiment binds the new config/secret.
- The runner compares only secret hashes and writes numeric rewards, so the CLI output remains free of raw secret values while still proving the bound-secret behavior.
- Updated the completion audit and progress dashboard to remove this item from the active high-risk proof gaps.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_experiment_runs_keep_bound_secret_after_project_secret_change tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 CLI Text File Payload Edge Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_text_file_payloads_reject_bad_files_without_side_effects`.
- The test covers `project init --config`, `project config import --config`, `project secret set --value-file`, `submit --summary-file`, `submit --feedback-file`, `annotate add --body-file`, and `annotate edit --body-file` against invalid UTF-8 files, directories used as files, and unreadable files when the platform enforces file permissions.
- It verifies stable `CONFIG_INVALID` error blocks, no stdout, no SQLite writes, and no watched filesystem changes for each payload failure.
- Fixed `src/alab/configs.py::load_project_config` so directory, invalid UTF-8, and unreadable project config files now map to `CONFIG_INVALID` instead of escaping as system errors.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_text_file_payloads_reject_bad_files_without_side_effects tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/configs.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/configs.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Git Commit SHA Selector Disambiguation

Implemented:

- Added explicit Git object disambiguation for commit SHA selectors in `src/alab/services.py::_resolve_commit_sha_selector`.
- `latest`, `final`, `best`, and full/unambiguous SHA selectors still resolve to concrete commits, while ambiguous SHA prefixes now fail with stable `CONFIG_INVALID` instead of relying on raw Git diagnostics.
- Added `tests/test_cli_contract.py::test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity`.
- The test covers abbreviated SHA acceptance for `exp create --from-commit`, `exp checkout --commit`, and annotation path/line targets, plus ambiguity rejection without DB or filesystem side effects for experiment creation, inspection checkout, and annotation creation.
- Updated the completion audit and progress dashboard to remove Git SHA selector abbreviation/ambiguity from the active high-risk CLI proof gaps.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity tests/test_cli_contract.py::test_alab_object_selectors_require_complete_ids tests/test_cli_contract.py::test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_experiment_checkout_success_fields_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/services.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Public Safe Status Negative-Field Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields`.
- The test creates public-status fixtures containing project history, experiment/run/annotation records, env values, `secret_env` names and values, runner-command/log/artifact markers, hidden log and hidden-asset rows, absolute catalog/cache paths, adapter staging path markers, and failed-baseline log markers.
- It verifies no-key valid public status keeps the documented public shape and no-key invalid public status keeps the reduced public-invalid shape, with no forbidden private/runtime fragments in either output.
- Updated the completion audit and progress dashboard so the public safe status row now has direct negative-field evidence.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields tests/test_cli_contract.py::test_status_object_type_tracks_context_mode tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Regenerated Token Private Annotation Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights`.
- The test creates an experiment-private annotation from the worktree token context, regenerates that worktree token through an admin command, then proves the same experiment context can still show and edit the private annotation after the original raw token is revoked.
- It verifies the context marker moves to the new token id, the old token row is revoked, the new token row is active, the raw token value changes, and annotation revision creator metadata remains experiment-bound rather than raw-token-bound.
- Updated the completion audit and progress dashboard to remove regenerated-token private annotation visibility/editing from the active high-risk proof gaps while keeping broader visibility matrix rows `PARTIAL`.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Admin Private-To-Exp Annotation Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit`.
- The test creates an admin-authored private annotation targeting one experiment while binding visibility to another experiment through `--private-to-exp`.
- It proves the target experiment token cannot show, edit, or archive that private annotation, while the selected creator experiment token can show, edit, archive, and remove it.
- It verifies stored `visibility_json`, annotation creator metadata, revision creator metadata, final row deletion, dry-run/final `deleted revisions`, and remove audit `deleted_revision_count`/filesystem metadata.
- Updated the completion audit and progress dashboard so admin `--private-to-exp` and this private remove-audit path are no longer stale proof gaps, while broader annotation authorization matrices remain `PARTIAL`.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Runner Operation Cleanup Coverage

Implemented:

- Extended local, Docker, Harbor, SkyDiscover Python, and SkyDiscover Docker focused tests with service-level operation cleanup assertions.
- `tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed` now writes marker files into the runner temp workspace/run directories, then proves validation and run operation directories are removed and the visible experiment worktree remains unchanged.
- Harbor and SkyDiscover smoke tests now assert validation/run temp dirs are gone after capture and that runner execution leaves the experiment worktree visibly clean.
- `tests/test_runner_docker.py::test_project_init_persists_docker_setup_output_as_hidden_validation_logs` now covers both fake-Docker validation and fake-Docker experiment run cleanup/worktree immutability.
- Updated the completion audit and progress dashboard to remove default-path runner temp-dir cleanup from the active high-risk proof gaps while keeping real-environment runner confirmation separate.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_runner_docker.py::test_project_init_persists_docker_setup_output_as_hidden_validation_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_docker.py`
- `git diff --check`

## 2026-05-21 Home Id And Tag Edge Coverage

Implemented:

- Extended `tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint` with home-id suffix checks for the V1 22-character unpadded base64url shape decoding to 16 bytes.
- Extended `tests/test_smoke.py::test_capability_help_and_preflight_surfaces` so an inspection checkout directly attempts `exp tag add` and receives `COMMAND_UNAVAILABLE`.
- Extended `tests/test_smoke.py::test_config_source_observe_and_tags` so adding `BASELINE` after `baseline` proves lowercase slug normalization and duplicate-tag idempotency in both rendered output and SQLite rows.
- Updated the completion audit and progress dashboard so home-id entropy is no longer an active high-risk backlog item, while the tags row keeps only the remaining visibility-expansion proof gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_smoke.py`

## 2026-05-21 Tag Authorization No-Expansion Coverage

Implemented:

- Extended `tests/test_smoke.py::test_config_source_observe_and_tags` with direct root tag-add and admin tag-remove assertions, keeping the existing owning-token tag flow and duplicate normalized tag coverage.
- Extended `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility` so project visibility is narrowed to `none`, then same-tag experiment lists from a worktree token and an inspection token prove tags only filter already-visible experiments instead of expanding authorization.
- Updated the completion audit to mark the Tags row as proved for default token/admin/root/inspection contexts.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`

## 2026-05-21 Experiment Search Corpus Coverage

Implemented:

- Extended `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility` with explicit search corpus assertions for project task text, experiment goals, tags, final summary, final feedback, and case-insensitive matching.
- Kept the same test's existing negative corpus assertions for stdout, stderr, artifact bytes, historical annotation revisions, and private annotation visibility, making the search corpus/privacy audit row directly evidenced in one focused path.
- Updated the completion audit and progress dashboard to mark the default local experiment search corpus/privacy surface as proved.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Experiment Observe Filter And Sort Matrix Closure

Implemented:

- Extended `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`.
- The test now pins experiment created/updated timestamps and covers `created`, `updated`, `name`, and `status` sort fields directly.
- Added status filter coverage for open, closed, and archived experiments, including archived inclusion.
- Added repeated `--tag` AND coverage through a dedicated two-tag experiment.
- Added a distinct inline source experiment so `--source-id` filtering proves exclusion across multiple source ids instead of only matching the default source.
- Added focused search-path coverage for source, tag, name, status, and name-sort filters using the same experiment row helper.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so experiment list/search/best filter, pagination, and sort matrices are no longer active work. Remaining active evidence is grouped audit-row decomposition plus release gates.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`

## 2026-05-21 Observe List Filter And Sort Matrix Closure

Implemented:

- Extended `tests/test_smoke.py::test_observe_list_pagination_contracts`.
- The test now covers run filters for experiment, status, config version, commit prefix, reward range, runner type, exit code, failure reason, started/ended ranges, archive inclusion, and sort fields including reward null-last ordering.
- The same test covers artifact filters for experiment, run, validation, root, status, path query, content hash, created range, size range, archive inclusion, and artifact sort whitelists.
- The same test covers log filters for experiment, run, validation, stream, truncated, created range, archive inclusion, and log sort whitelists.
- The same test covers annotation filters for target type, target id, target alias, author, created-by, private, query, created/updated ranges, archive inclusion, and annotation sort whitelists.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so run/artifact/log/annotation list filter/sort matrices are no longer active work. Remaining observe evidence is experiment list/search filter/sort row mapping.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_observe_list_pagination_contracts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_observe_list_pagination_contracts tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Annotation Target Resolution Coverage

Implemented:

- Added `tests/test_smoke.py::test_annotation_path_targets_resolve_commits_and_reject_dirty_shorthand`.
- The test proves annotation object targets for experiments, runs, and artifacts, plus explicit path targets with `HEAD`, `head`, `latest`, `final`, `best`, and an unambiguous commit SHA prefix.
- It verifies resolved commits and stored `target_json` use concrete commit SHAs rather than moving aliases.
- It proves path targets may point to Git trees, line targets require blobs, invalid line ranges and normalized repo-path failures reject without creating annotations, and current-worktree shorthand rejects staged, unstaged, deleted, renamed, copied, and untracked changes.
- Updated the completion audit and progress dashboard to mark annotation target resolution as proved for default CLI/storage surfaces.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_annotation_path_targets_resolve_commits_and_reject_dirty_shorthand -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Log And Artifact Access Coverage

Implemented:

- Extended `tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation` so `logs show` proves byte-limited stored log content is rendered from the same truncated/redacted bytes that `logs export` writes.
- Extended `tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs` so token contexts directly reject `logs show --include-hidden`, and Harbor hidden-log backing files are asserted not to have artifact rows.
- Extended the SkyDiscover Python and Docker smoke tests so hidden evaluator log backing files are asserted not to have artifact rows.
- Updated the completion audit and progress dashboard to mark default local log access and artifact export, plus adapter hidden-output non-artifact behavior, as proved.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`

## 2026-05-21 Experiment Best Ranking Coverage

Implemented:

- Extended `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility` with direct best-ranking assertions after the existing search/visibility path.
- Added controlled tie experiments and synthetic run rows to prove one output block per experiment when multiple runs qualify, newest qualifying run selection within an experiment, tie ordering by ended time then experiment id, and exclusion of high-reward `running`/`failed`/`error`/`timeout`/`interrupted` plus unparsed passed runs.
- Updated the completion audit and progress dashboard to mark the default local experiment best surface as proved while keeping broader completion and full-suite gates open.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`

## 2026-05-21 Progress Dashboard Pipeline Split

Implemented:

- Reduced `docs/progress.md` to a short dashboard covering only current position, completion gates, recently closed gaps, and the pointer to the next work file.
- Added `docs/progress_pipeline.md` as the authoritative active queue, with explicit operating rules, active batches, closed evidence gaps, full-suite policy, and an update checklist.
- Added synchronized Chinese dashboard/pipeline files and updated README and completion-audit pointers so future agents do not use the historical log as a backlog.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `git diff --check`
- `rg -n "[ \t]+$" README.md README_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 Annotation Authorization Matrix Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations`.
- The test proves project-visible peer annotations are readable but not editable/archiveable/unarchiveable/removable by the target experiment token, including after the creator archives the annotation.
- It proves archived annotations are hidden from default list output but still visible by id and through `--include-archived`, while archive status does not grant lifecycle mutation rights.
- It proves current project visibility still caps annotation visibility, private peer annotations stay hidden from the target experiment, and inspection contexts can read visible annotations but cannot run `annotate add/edit/archive/unarchive/remove`.
- Updated the completion audit and progress pipeline so the annotation visibility/lifecycle row is no longer an active P0 proof gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Optional Warning Output Closure

Implemented:

- Added `tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry`.
- The test proves a failed ALab-owned Docker image prune renders an `object: warning` block with `DOCKER_CACHE_PRUNE_FAILED`, keeps the cache entry active, and records the warning count in audit metadata.
- Updated the completion audit and progress pipeline so optional warning outputs are no longer an active CLI long-tail gap. Remaining CLI focus is saved-result tails, less-used aliases, and command-specific `SCOPE_VIOLATION`/archived/config/output/lifecycle blocker matrices.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_cli_contract.py::test_source_import_warning_success_fields_follow_cli_spec tests/test_cli_contract.py::test_context_token_file_permission_warning_renders_after_primary_result tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Alias Group Boundary Closure

Implemented:

- Added `tests/test_cli_contract.py::test_registered_alias_groups_are_limited_to_covered_observe_surfaces`.
- The test enumerates every current handler-backed command alias group and proves there are no less-used alias groups outside the already covered observe/read/lifecycle surfaces.
- Updated the completion audit and pipeline so alias work is no longer an active CLI long-tail item; remaining CLI focus is saved-result tails and command-specific error/blocker matrices.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_command_registry_paths_aliases_and_matcher_are_stable tests/test_cli_contract.py::test_registered_alias_groups_are_limited_to_covered_observe_surfaces tests/test_cli_contract.py::test_observe_read_aliases_render_equivalent_outputs tests/test_cli_contract.py::test_observe_lifecycle_aliases_render_canonical_shapes tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Saved Result Tail Closure

Implemented:

- Added `tests/test_cli_contract.py::test_saved_result_failure_tails_have_stable_cli_shape`.
- The test fixes the shared saved-result tail contract for baseline failures, run failures, reward-parse failures including the `error` parse status, and submission failure blocks.
- Updated the completion audit so registered success schemas and saved result-failure rendering are no longer active CLI long-tail gaps for current local/default/fake runner surfaces.
- Updated the pipeline so the remaining CLI long-tail is the command-specific error/blocker matrix.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_saved_result_failure_tails_have_stable_cli_shape tests/test_cli_contract.py::test_project_baseline_result_failures_follow_cli_spec tests/test_cli_contract.py::test_run_result_failures_follow_cli_spec tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_cli_contract.py::test_project_validate_result_failures_follow_cli_spec tests/test_cli_contract.py::test_submit_result_failures_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Run Reward Parse Failure Matrix Coverage

Implemented:

- Added `tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit`.
- The test proves run-level saved result failures for file rewards containing `NaN`, `Infinity`, empty strings, and non-numeric text.
- It also proves the nonzero-exit plus invalid reward case keeps run status `failed`, renders `RUNNER_FAILED`, and stores the invalid reward parse status without replacing the runner failure reason.
- Updated the completion audit and progress pipeline so local reward-parse variants are no longer listed as an active saved-failure proof gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_cli_contract.py::test_run_result_failures_follow_cli_spec tests/test_cli_contract.py::test_project_validate_result_failures_follow_cli_spec tests/test_cli_contract.py::test_submit_result_failures_follow_cli_spec tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Docker Unavailable Saved Failure Coverage

Implemented:

- Extended `tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error` with exact project-init failure field ordering and exit-code assertions.
- Added `tests/test_runner_docker.py::test_docker_unavailable_run_is_saved_result_failure`.
- The new test creates a valid fake-Docker project, then makes Docker unavailable during `alab run` and proves the saved run result exits `1`, renders `RUNNER_ERROR`, stores `status=error` and `reward_parse_status=not_attempted`, and captures the Docker missing reason as stderr log metadata.
- Updated the completion audit and progress pipeline so Docker-unavailable saved failures are no longer an active saved-failure proof gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error tests/test_runner_docker.py::test_docker_unavailable_run_is_saved_result_failure tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Python Dependency Saved Failure Coverage

Implemented:

- Strengthened `tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results`.
- The test now proves fake-`uv` dependency installation failures remain saved result failures for both baseline validation and experiment run paths, exit `1`, render the expected result failure fields, persist error records, capture setup output only in hidden logs, and do not leak a debug traceback under `ALAB_DEBUG=1`.
- Updated the completion audit and progress pipeline so dependency-installation saved failures are no longer an active saved-failure proof gap for the default/fake SkyDiscover Python path.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Pipeline Focus Maintenance

Implemented:

- Kept `docs/progress.md` as a short dashboard and made `docs/progress_pipeline.md` carry the current active batch explicitly at the top.
- Updated the CLI success-schema audit row so public/public-invalid `status`, observe read aliases, observe lifecycle aliases, and hidden-log default shapes are recorded as already-proved evidence rather than remaining examples.
- Added observe alias closure to the dashboard and pipeline closed-gap lists so future batches do not reopen already-proved output variants.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 CLI Capability Payload Preflight Audit Narrowing

Implemented:

- Tightened `tests/test_cli_contract.py::test_object_specific_not_found_errors_stay_precise_for_root_admin_selectors` so it asserts every documented not-found code with a current runtime selector is covered, while explicitly excluding `CACHE_NOT_FOUND` because V1 has no cache-id selector command.
- Updated the completion audit to distinguish proved generated payload/capability preflight variants from still-open command-error matrix work.
- Narrowed the pipeline's active CLI batch to optional warning blocks, less-used aliases, and command-specific `SCOPE_VIOLATION`/archived/config/output/lifecycle blocker matrices.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_object_specific_not_found_errors_stay_precise_for_root_admin_selectors tests/test_cli_contract.py::test_locked_commands_preflight_before_handler_argument_effects tests/test_cli_contract.py::test_nested_help_uses_same_locked_preflight_with_handler_payloads tests/test_cli_contract.py::test_explicit_credentials_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_project_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_experiment_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_inspection_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_explicit_keys_preserve_context_conflict_before_handler_effects tests/test_cli_contract.py::test_text_file_payloads_reject_bad_files_without_side_effects tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Source-Dependent Missing-Path Saved Failure Coverage

Implemented:

- Extended `tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit` so submit `--rerun` with a missing file reward is rendered as a saved submission failure with `REWARD_PARSE_ERROR`, no traceback, no stored submission, and a persisted failed run record.
- Extended `tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors` with exact baseline/run field-label assertions and submit `--rerun` wrapping for a missing Docker context.
- Updated the completion audit and progress pipeline so source-dependent missing-path saved failures are no longer an active saved-failure proof gap for local runner working directories, file rewards, Dockerfiles, and Docker contexts on default/fake surfaces.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py tests/test_runner_docker.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py tests/test_runner_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Docker Setup Saved Failure Coverage

Implemented:

- Added `tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures`.
- The test proves Docker image pull failures and Dockerfile build failures are saved result failures for both baseline validation and experiment run paths, exit `1`, render `RUNNER_ERROR` or `BASELINE_VALIDATION_FAILED` result tails, persist `status=error` with `reward_parse_status=not_attempted`, expose only stable visible stderr reasons, and store setup stdout/stderr as hidden logs.
- Updated the completion audit and progress pipeline so Docker pull/build saved failures are no longer an active saved-failure proof gap for fake/default Docker paths.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error tests/test_runner_docker.py::test_docker_unavailable_run_is_saved_result_failure tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Adapter Docker Build Saved Failure Coverage

Implemented:

- Added `tests/test_smoke.py::test_adapter_docker_build_failures_are_saved_results`.
- The test proves Harbor separate-verifier Dockerfile build failures and SkyDiscover Docker evaluator build failures are saved result failures for both baseline validation and experiment run paths.
- It asserts rendered failure fields, persisted `status=error` and `reward_parse_status=not_attempted`, stable visible stderr reasons, and hidden setup stdout/stderr logs.
- Updated the completion audit and progress pipeline so adapter-specific Docker build/setup saved failures are no longer an active saved-failure proof gap for fake/default paths.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_adapter_docker_build_failures_are_saved_results -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_adapter_docker_build_failures_are_saved_results tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Dashboard/Pipeline Separation Cleanup

Implemented:

- Reduced `docs/progress.md` to a true short dashboard: gate states, one-line active focus, and high-level do-not-reopen summary only.
- Kept the detailed closed-gap list in `docs/progress_pipeline.md` and added explicit maintenance rules to rewrite stale queue rows instead of appending duplicate backlog.
- Synchronized the Chinese dashboard and pipeline updates.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Archived/Closed/Removed State Error Matrix

Implemented:

- Added `tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem`.
- The test covers `PROJECT_ARCHIVED` for `exp create`, `run`, and `submit`, `EXPERIMENT_CLOSED` for `run` and `submit`, and removed-worktree `SCOPE_VIOLATION` for `run` and `submit`.
- Each case asserts the stable error block, exit `4`, exact reason, `next: none`, and no database or watched filesystem mutations.
- Updated the completion audit and progress pipeline so archived/closed/removed-state experiment command errors and hard-remove lifecycle blockers are no longer active CLI-row gaps.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Export Output Error Matrix Audit Closure

Implemented:

- Reviewed existing export-output evidence and updated the completion audit and progress pipeline instead of adding duplicate tests.
- `tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks` already covers project config, artifact, and log export `OUTPUT_EXISTS`, directory target rejection, overwrite success, artifact/log missing-parent preflight, and no database/config mutation.
- The active CLI command-error matrix is now narrowed to remaining config-value branches and broader visibility `SCOPE_VIOLATION` selectors.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md tests/test_cli_contract.py` returned no matches.

## 2026-05-21 Visibility Scope Selector Error Matrix

Implemented:

- Added `tests/test_cli_contract.py::test_visibility_scope_selector_errors_are_non_disclosing_and_side_effect_free`.
- The test creates peer experiment, run, artifact, log, and annotation records, then lowers visibility to `none` and proves the first experiment token gets stable non-disclosing `SCOPE_VIOLATION` errors for each peer selector.
- Each selector assertion checks exit `4`, exact reason, absence of the corresponding `*_NOT_FOUND` code, and no database or watched filesystem mutation.
- Updated the completion audit and progress pipeline so broader visibility `SCOPE_VIOLATION` selectors are no longer an active CLI-row gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_visibility_scope_selector_errors_are_non_disclosing_and_side_effect_free tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Config-Version Error Matrix Closure

Implemented:

- Added `tests/test_cli_contract.py::test_config_version_value_errors_preserve_database_and_filesystem`.
- The test covers project config show/export `active-valid` when no active config exists, missing explicit config versions, non-numeric version selectors, `exp best` without an active config, and `exp best --config-version` for a missing config version.
- Each case asserts the stable error block, exit code, exact reason, `next: none`, and no database, watched filesystem, or export-output mutation.
- Updated the completion audit and progress pipeline so the CLI command-error matrix is no longer an active proof gap; the current active batch is now hidden asset/log and adapter failure cleanup edges.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_config_version_value_errors_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_config_version_value_errors_preserve_database_and_filesystem tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Python Non-Import Proof

Implemented:

- Extended `tests/test_runner_skydiscover.py::test_skydiscover_python_runner_materializes_hidden_bundle_and_metrics`.
- The test now proves the evaluator module is imported in the wrapper subprocess, not in the main ALab process, by comparing evaluator import pid against the current process and asserting the wrapper module is absent from main-process `sys.modules`.
- The same test continues to prove hidden bundle materialization, visible `sandbox: not-os-sandbox` disclosure, and non-disclosure of evaluator source/stdout/paths in visible stdout.
- Updated the runner/adapters audit row and progress pipeline so this SkyDiscover Python default/fake proof gap is closed.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_python_runner_materializes_hidden_bundle_and_metrics -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_skydiscover.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Reward Parser Matrix Closure

Implemented:

- Added `tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits`.
- Added `tests/test_runner_harbor.py::test_harbor_reward_parser_handles_json_text_missing_and_invalid_values`.
- Updated Harbor `reward.json` parsing so a present primary metric that is non-numeric or non-finite is `invalid`, while an absent primary metric remains `missing`, matching the reward parsing spec.
- Updated the runner/adapters audit row and progress pipeline so reward extraction is proved for default/fake paths and only real adapter environments remain environment-gated.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py::test_harbor_reward_parser_handles_json_text_missing_and_invalid_values tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Log Chronology Cleanup

Implemented:

- Kept `docs/progress.md` and `docs/progress_cn.md` as 46-line dashboards, with `docs/progress_pipeline.md` and `docs/progress_pipeline_cn.md` carrying the active queue and closed-gap guardrails.
- Moved the SkyDiscover Python non-import and reward parser matrix closure entries to the end of the chronological progress log after the config-version closure, matching the actual latest implementation order.
- Aligned the Chinese log ordering with the English canonical log for the optional warning and run reward parse failure sections.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 Artifact Blob Lifecycle Closure

Implemented:

- Added `tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting`.
- The test creates identical artifact bytes from a baseline validation and an experiment run, proves both rows share one blob path, removes the validation artifact without deleting the shared blob, then removes the run artifact and proves the final reference deletes the blob through trash staging.
- Updated the runner/adapters audit row and progress pipeline so artifact capture and blob lifecycle default local/storage paths are no longer an active proof gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Runner/Adapter Focus Refresh

Implemented:

- Updated the short dashboard and active pipeline focus after artifact/log lifecycle closure.
- The active runner/adapter queue now points at remaining shared-runner edge mapping, adapter failure cleanup, Harbor unsupported-field mapping, and SkyDiscover catalog/source precedence gaps instead of the already-closed artifact/log lifecycle family.
- Added artifact/log capture and reference-counted deletion to the do-not-reopen summaries.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Log File Lifecycle Closure

Implemented:

- Added `tests/test_smoke.py::test_shared_log_file_reference_counting`.
- The test duplicates one stored log row so two log records reference the same file path, removes the first log without deleting the shared file, then removes the second log and proves the final reference deletes the file through trash staging.
- Updated the runner/adapters audit row and progress pipeline so logs and hidden logs default local/adapter paths are no longer an active proof gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_shared_log_file_reference_counting -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting tests/test_smoke.py::test_shared_log_file_reference_counting tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation tests/test_smoke.py::test_global_preview_bytes_controls_validation_and_run_log_previews tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Harbor Unsupported Field Matrix Closure

Implemented:

- Expanded `tests/test_runner_harbor.py::test_harbor_task_rejects_unsupported_fields` into a parameterized matrix.
- The matrix now maps the Harbor spec's strict unsupported categories: multi-step tasks, non-Linux OS/platform, GPU and `gpu_types`, `storage_mb`, MCP servers, healthchecks, custom scheduling, external services, Docker Compose or multi-container runtime, host environment placeholders, raw Docker args, and task-declared host mounts.
- Updated `docs/completion_audit.md`, `docs/progress.md`, and `docs/progress_pipeline.md` so Harbor unsupported-field mapping is a closed default/fake proof gap rather than active work. Real Docker-backed Harbor validation remains release-gated.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py::test_harbor_task_rejects_unsupported_fields -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_harbor.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_harbor.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_harbor.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Catalog And Source Precedence Closure

Implemented:

- Extended `tests/test_smoke.py::test_skydiscover_catalog_ref_validation` to prove catalog refs use the pinned local checkout: resolving a path added only in a newer upstream commit fails until an explicit catalog update runs.
- The same test now proves dirty local catalog update rejection, no update audit on rejection, and successful update after cleanup.
- Added `tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections` for `--source-ref` rejection, explicit source conflict rejection, matching explicit-source acceptance, derived-source metadata retention, and no whole-benchmark/private-file source import.
- Added `tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program` for explicit `--source-git` and `--source-empty` success when no initial program exists.
- Updated the audit and pipeline so SkyDiscover source precedence is no longer active work. The remaining SkyDiscover catalog gaps are now narrowed to removal blockers, unexpected remote rejection, and post-removal history observability.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_harbor.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_harbor.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_runner_harbor.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Catalog Removal And History Closure

Implemented:

- Added `tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history`.
- The test proves `catalog skydiscover remove` blocks active project configs and open experiments that still reference `skydiscover:` refs, with no remove audit and no catalog path deletion on rejection.
- The test also proves update rejects an unexpected local catalog remote before fetch/update, with no update audit.
- After archiving the dependent project and experiment, the same test removes the catalog, verifies removed catalog metadata and local path deletion, then shows existing experiment, run, and log history without the catalog checkout present.
- Updated the audit and pipeline so SkyDiscover catalog/ref default local-Git paths are closed; only live upstream/network validation remains environment-gated.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Docker Artifact Feedback Closure

Implemented:

- Extended `tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs`.
- The fake Docker evaluator now returns JSON `artifacts` feedback and writes `captured.txt` into the mounted workspace.
- The test proves JSON `artifacts` stay in `record_json.adapter_feedback.feedback`, while only the configured `workspace:captured.txt` glob creates artifact rows for both baseline validation and experiment run records.
- Updated the audit and pipeline so SkyDiscover Docker artifact-feedback mapping is no longer active work; real Docker execution remains environment-gated.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_docker_runner_builds_hidden_bundle_and_parses_metrics tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_skydiscover.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_runner_skydiscover.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Shared Runner And Adapter Failure Cleanup Closure

Implemented:

- Added `tests/test_runner_docker.py::test_docker_runner_timeout_removes_named_container_and_redacts_output` for Docker timeout container cleanup and secret redaction.
- Added Harbor adapter failure coverage for resolver-unavailable, incomplete-resolver, wrong-target-kind, and missing-working-directory branches that must not create runtime dirs, plus timeout cleanup for the named verifier container.
- Added SkyDiscover adapter failure coverage for Python/Docker resolver-unavailable, incomplete-resolver, wrong-target-kind, and missing-program-path branches that must not create runtime dirs, plus SkyDiscover Docker timeout cleanup for the named evaluator container.
- Extended `tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs` to simulate a deleted local catalog checkout after a valid project/run, proving validation and run failures are saved, operation temp dirs are removed, and the visible experiment worktree stays clean.
- Updated the dashboard, pipeline, and audit so shared-runner edge mapping and adapter failure cleanup are closed for current default/fake paths; remaining runner validation is real-environment gated.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_runner_timeout_removes_named_container_and_redacts_output tests/test_runner_harbor.py::test_harbor_adapter_resolver_failures_do_not_create_runtime_dirs tests/test_runner_harbor.py::test_harbor_timeout_removes_named_container_and_keeps_output_hidden tests/test_runner_skydiscover.py::test_skydiscover_adapter_resolver_failures_do_not_create_runtime_dirs tests/test_runner_skydiscover.py::test_skydiscover_docker_timeout_removes_named_container_and_keeps_output_hidden tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Project Config Schema Proof Mapping Closure

Implemented:

- Added `tests/test_runner_local.py::test_project_config_schema_maps_runner_reward_and_env_edges`.
- The test maps remaining runner/reward/artifact/env schema edges: schema version, runner type/env mode, timeout bounds, normalized runtime path escapes including Windows and NUL shapes, Docker host-network rejection, raw Docker passthrough rejection, Docker image/Dockerfile/context mutual requirements, platform selector aliasing and invalid selector rejection, build/env string-map strictness, adapter ref requirements, reward-type required fields, artifact/log limit shapes, public-source limit shapes, and explicit-visibility requirements.
- Tightened `ProjectConfig` so `runner.platform` rejects non-V1 selectors such as `windows/amd64` at schema validation while preserving Linux alias canonicalization such as `Linux/X64 -> linux/amd64`.
- Updated the audit, dashboard, and pipeline so project config/schema proof mapping is closed for current schema/default source-dependent paths. The active P0 queue now moves to canonical object relationship invariants.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_project_config_schema_maps_runner_reward_and_env_edges tests/test_runner_docker.py::test_docker_platform_aliases_are_canonicalized_for_cache_and_cli tests/test_runner_docker.py::test_project_init_rejects_unsupported_docker_platform_architecture -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py::test_docker_platform_aliases_are_canonicalized_for_cache_and_cli tests/test_runner_docker.py::test_project_init_rejects_unsupported_docker_platform_architecture tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/configs.py tests/test_runner_local.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/configs.py tests/test_runner_local.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/configs.py tests/test_runner_local.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Guardrail Split

Implemented:

- Split duplicate-work guardrails out of `docs/progress_pipeline.md` into `docs/progress_closed_gaps.md`.
- Added synchronized `docs/progress_closed_gaps_cn.md`.
- Shortened `docs/progress_pipeline.md` so it now carries only the active batch, active queue, guardrail pointer, full-suite policy, and update checklist.
- Updated `docs/progress.md`, `README.md`, `AGENTS.md`, `docs/completion_audit.md`, and this log to point at the new dashboard/pipeline/guardrail/log/audit reading path.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" README.md README_cn.md AGENTS.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 Project And Experiment Retained-Row Invariant Closure

Implemented:

- Extended `tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths`.
- Extended `tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash`.
- The tests now assert that experiment/project hard remove deletes primary rows while retaining `path_registry` rows as `removed`, retaining credentials as `revoked`, preserving non-null removal/revocation timestamps, and aligning `path_registry.removed_by_credential_id` with the remove audit actor credential.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so this retained-row invariant family is no longer vague active work. Remaining canonical object relationship work stays active for other object families and visibility joins.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Public From-Experiment Visibility Intersection Closure

Implemented:

- Extended `tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound`.
- The test now covers public `exp create --from-exp` against current project visibility `none`, current explicit project visibility with a listed and unlisted source experiment, and a source experiment whose stored explicit upper bound omits itself.
- The allowed explicit case asserts the stored `creation_origin.kind = from_exp`; the blocked explicit cases assert stable `SCOPE_VIOLATION`, no experiment row, and no worktree creation.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so public inheritance visibility intersection is no longer broad active work.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Source And Validation Hard-Remove Relationship Closure

Implemented:

- Extended `tests/test_smoke.py::test_config_source_observe_and_tags`.
- The test now proves source remove preserves immutable config-version reproducibility by blocking any source referenced by a stored project config version while preserving the source row and Git ref.
- The same path proves removable source hard remove deletes the source row and Git source ref, stores source-ref deletion metadata, and keeps archived dependent experiments as denormalized history.
- Validation remove now asserts the remove audit row carries the admin actor credential, generic action/object ids, cascade flag, and child artifact/log deletion metadata.
- Updated audit, dashboard, pipeline, and closed-gap guardrails so this source/validation relationship family is no longer broad active object-model work.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Maintenance Object Audit Metadata Closure

Implemented:

- Extended `tests/test_smoke.py::test_auth_init_and_config_show` to assert backup prune, zero-count cache prune, and stale lock clear audit actor/action/object/cascade/metadata rows.
- Extended `tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries` and `test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry` to assert trash/Docker-warning cache prune audit metadata, including actor, prune counts, and warning counts.
- Extended `tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history` to assert catalog remove audit actor/action/object/cascade/reason/schema metadata.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so backup/cache/lock/catalog maintenance audit metadata is no longer active object-model work. Remaining active evidence moved to visibility joins and grouped audit-row decomposition at that point.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Explicit Token And Inspection Visibility Closure

Implemented:

- Extended `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`.
- The test now imports explicit project visibility policies and proves a worktree token keeps own-experiment visibility while reading explicitly listed peer experiments, runs, artifacts, and logs.
- The same test proves an inspection token uses the same explicit visibility intersection, can read explicitly listed peer experiment/run records, and still receives non-disclosing `SCOPE_VIOLATION` for existing unlisted experiments.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so explicit token/inspection observe visibility joins are no longer active work. Remaining active evidence is observe filter/sort row mapping and grouped audit-row decomposition.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Experiment Observe Matrix Queue Refresh

Implemented:

- Closed the remaining experiment list/search/best filter, pagination, and sort matrix for current default local visible/admin paths.
- Updated `docs/progress.md` and `docs/progress_pipeline.md` so the active P0 is now grouped audit-row decomposition, not observe filter/sort work.
- Added the detailed closure record earlier in this log under `2026-05-21 Experiment Observe Filter And Sort Matrix Closure`.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Credential Audit Metadata Closure

Implemented:

- Extended `tests/test_smoke.py::test_auth_init_and_config_show` to assert root credential regenerate audit actor/action/object/cascade metadata, revoked credential references, and absence of raw root key material.
- Extended `tests/test_smoke.py::test_config_source_observe_and_tags` to assert admin key create/revoke audit actor/action/object/cascade metadata, revoke metadata, and absence of raw root/admin key material.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so credential audit metadata is no longer the weakest grouped audit-row evidence target. Remaining active evidence is the next grouped audit-row decomposition plus release gates.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Inspection Context Repair Pinned Commit Closure

Implemented:

- Extended `tests/test_smoke.py::test_context_self_repair_requires_registered_branch`.
- The test now creates a moved inspection checkout, proves self-token repair rejects a mismatched pinned inspection commit without changing the active registry row or writing a repair audit, then checks that returning to the pinned commit allows self-token repair.
- The successful repair path now asserts the active inspection `path_registry` row is updated and the `inspection_checkout` repair audit carries token actor/action/object/cascade fields plus schema-versioned context repair metadata.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so inspection context repair pinned-commit/audit metadata is no longer an active grouped context-repair gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Token Credential Side-Effect Evidence Mapping

Implemented:

- Mapped existing token regenerate/revoke evidence into the credential and audit rows instead of leaving it as a repeated broad gap.
- `tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec` proves token regenerate/revoke audit metadata, registered path hashes, and raw-token non-rendering in result/audit output.
- `tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights` proves old-token revocation, new-token activation, marker token-id update, raw token rotation, and private annotation continuity after regeneration.
- Updated the dashboard, pipeline, and closed-gap guardrails so token revoke/regenerate side-effect mapping is no longer queued as unresolved credential evidence.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Context Marker Conflict And Alias Closure

Implemented:

- Added `tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free`.
- The test proves symlink aliases resolve to the registered project context, exact missing markers fail as `CONTEXT_NOT_FOUND`, invalid marker JSON fails as `CONTEXT_CONFLICT`, wrong marker home ids fail for both `context show` and `context repair`, and marker/registry disagreement fails during context detection.
- Every failure branch asserts the `path_registry` snapshot and repair audit count remain unchanged.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so marker/registry disagreement, missing marker, symlink alias, and current marker/home mismatch variants are no longer active grouped context gaps.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free -q`

## 2026-05-21 Credential Model Proof Closure

Implemented:

- Hardened low-level credential verification so required-scope, project, token-mode, token-path, type-prefix/type-row, revoked-row, unknown-id, malformed, and verifier mismatch failures all return generic `AUTH_DENIED: invalid credential`.
- Added `tests/test_auth.py::test_credential_verification_failures_do_not_reveal_failure_part` for non-disclosing auth-denial variants.
- Added `tests/test_auth.py::test_credential_generation_uses_high_entropy_secret_and_salt_sources` to prove raw credential secrets use `secrets.token_hex(32)` and per-credential salts use `secrets.token_bytes(32)`.
- Added `tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free` to prove project admin keys can list only same-project credentials, cannot use root credential listing, cannot create/revoke credentials, and rejected authority paths leave the database unchanged.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so malformed credential variants, project-admin authority edges, and raw secret entropy/source generation are no longer active credential-model gaps.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_key_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_auth_root_regenerate_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_key_command_success_fields_follow_cli_spec -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_key_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_auth_root_regenerate_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/auth.py tests/test_auth.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/auth.py tests/test_auth.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/auth.py tests/test_auth.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 V1 Security Boundary Negative Proof Closure

Implemented:

- Added `tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts`.
- The test proves V1 has no encryption/grant/rewrap dependency roots or runtime import roots, and no implementation or migration schema artifacts for encrypted storage, grant files, public grants, token rewrap, DEKs, ciphertext, keyring, or cryptography.
- The test also pins the README and blueprint wording that ALab V1 is plaintext local storage and a collaboration boundary, not a strong local multi-user security product.
- Updated the audit, dashboard, pipeline, and closed-gap guardrails so encrypted-storage/grant/rewrap absence and public/status/hidden security-boundary mapping are no longer active V1-boundary gaps.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Closeout Gate And Capability-Refresh Mapping

Implemented:

- Mapped `config validate --refresh-capabilities` to the fake/default Docker capability cache tests, native-platform fallback test, and platform/resource pre-write rejection tests in the completion audit.
- Moved the active pipeline into closeout mode so future work starts only from named audit defects or explicit release-target environment gates.
- Kept real Docker, Harbor, live SkyDiscover, and network/native dependency checks as explicit `ENV-GATED` release validation instead of treating them as default-suite proof.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Public Git Credential-Helper Warning Proof

Implemented:

- Extended `tests/test_smoke.py::test_public_exp_create_inline_source_import` with an isolated no-helper Git config path for public `--source-git`.
- The test now proves public Git inline source import renders no `PUBLIC_GIT_CREDENTIAL_HELPER_USED` warning when `GIT_CONFIG_GLOBAL` has no helper and `GIT_CONFIG_NOSYSTEM=1`, while the existing isolated helper path still renders the warning and persists it in source-origin metadata.
- Updated the completion audit, dashboard, pipeline, and closed-gap guardrails so public `--source-git` helper-available/helper-unavailable warning behavior is no longer an active public inline source gap.
- Marked the full default-suite gate stale because this batch changed tests and documentation after the closeout full-suite pass.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Context Repair Old-Path Blocker Proof

Implemented:

- Extended `tests/test_smoke.py::test_context_self_repair_requires_registered_branch` with a duplicate copied worktree that has a valid marker/token while the original registered worktree path still exists.
- The test now proves self-token `context repair` fails with `CONTEXT_CONFLICT: registered path still exists` and leaves the active `path_registry` row plus repair audit count unchanged.
- Updated the completion audit, dashboard, pipeline, and closed-gap guardrails so old registered-path-still-exists blockers are no longer an active context repair gap.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free tests/test_cli_contract.py::test_project_context_repair_accepts_ambient_admin_key -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Project Config Edit Semantics Proof Mapping

Implemented:

- Reclassified the runtime baseline trigger and config edit semantics audit row as proved for current config mutation surfaces.
- Mapped `tests/test_smoke.py::test_project_config_validation_edges` to the exact spec rules for latest-attempted edits, runtime baseline triggers, byte-identical no-op edits, metadata-only inherited edits, monotonic revert versions, and `project config set/import --dry-run` no-write behavior.
- Kept invalid runtime preservation and output/preflight evidence linked through the existing smoke and CLI-contract tests.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads tests/test_cli_contract.py::test_project_config_mutation_and_validate_success_fields_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Project Init Precedence Proof Mapping

Implemented:

- Reclassified the project-init input precedence audit row as proved for current local/Git/empty/Harbor/SkyDiscover init paths.
- Mapped direct evidence for mode-specific source-origin requirements, duplicate init option rejection, source-ref injection/mismatch cleanup, source-limit failures before rows/staged paths, malformed/negative source limit pre-write failures, retained invalid project baseline failures, one-time raw admin key rendering, and adapter-derived editable-source precedence/conflict/fallback paths.
- Kept the full default-suite gate stale because this is a documentation/test batch after the closeout pass.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_project_init_source_ref_mismatch_cleans_staged_paths tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error tests/test_smoke.py::test_harbor_project_init_uses_declared_source_and_excludes_private_assets tests/test_smoke.py::test_adapter_init_rejects_conflicting_explicit_source tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_cli_contract.py::test_project_init_mode_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_init_adapter_mode_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_one_time_raw_key_outputs_follow_cli_secret_rules tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Source Import Tree-Hash And Remote-Git Fidelity Proof

Implemented:

- Corrected `canonical_tree_hash` to sort manifest entries globally by repo-relative path and to include symlinked directory entries instead of skipping them during `os.walk` traversal.
- Updated source copying so plain and Git worktree imports preserve symlinked directories as symlink entries, while still rejecting Git submodules/gitlinks.
- Added `tests/test_smoke.py::test_canonical_tree_hash_manifest_matches_v1_spec` for the exact `alab-tree-sha256-v1` manifest entry order and regular-file/executable/symlink entry content.
- Extended `tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules` to cover standalone remote `source import --source-git --source-subdir`, including filtered subdir contents, stored canonical tree hash, resolved commit metadata, sanitized origin metadata without raw source URL/path, and no admin warning.
- Reclassified the source model/source import audit row as proved for current local/Git/empty source import/model paths and added the closed guardrail.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_canonical_tree_hash_manifest_matches_v1_spec tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived tests/test_smoke.py::test_source_import_empty_after_filter_warns tests/test_cli_contract.py::test_source_import_origin_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_source_import_warning_success_fields_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/source_import.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/source_import.py tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/source_import.py tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Experiment Create Source-Binding Proof Mapping

Implemented:

- Reclassified the experiment-create source-binding/default-source audit row as proved for current exp-create source-binding paths, with broader visibility still tracked in the dedicated visibility row.
- Mapped direct evidence for default-source creation, inline local/Git/empty/subdir imports, source dedupe, public source-import policy ceilings and disabled-public behavior, admin archived-source `--source-ref` binding, `--from-exp` latest/final/best/SHA resolution, closed/archived source-experiment behavior, mutable override narrowing, token creation with raw-token non-rendering, and selector/conflict no-write failures.
- Added a closed guardrail so future batches do not reopen `exp create` source-binding work unless a new selector, metadata field, token mode, mutable field, or visibility scope is introduced.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_admin_exp_create_can_bind_archived_source_ref tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_cli_contract.py::test_experiment_create_inline_source_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_experiment_create_from_exp_success_fields_follow_cli_spec tests/test_cli_contract.py::test_experiment_create_source_ref_success_fields_follow_cli_spec tests/test_cli_contract.py::test_non_remove_documented_conflicts_fail_without_side_effects tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Run And Submit Lifecycle Proof Mapping

Implemented:

- Reclassified the run/submit lifecycle audit row as proved for current local/default run-submit paths, while keeping adapter-specific runner result failures in the runner rows.
- Mapped direct evidence for parser preflight, byte limits, project/experiment/worktree state blockers, operation locks, stale running-record interruption, invalid Git states, running-record-before-auto-commit ordering, mutable-scope rollback and metadata, contextless runner workspaces, final-run success and failure behavior, summary/feedback/ref input rules, secret-value rejection, non-disclosing invisible/missing ref failures, and no final-submission rows on failed/timeout/error runs.
- Added a closed guardrail so future batches do not reopen run/submit lifecycle work unless run/submit gains new Git-state checks, mutable-scope semantics, ref visibility rules, payload modes, result statuses, or operation-lock behavior.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_rejects_invalid_git_states tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_cli_contract.py::test_run_result_failures_follow_cli_spec tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_cli_contract.py::test_submit_result_failures_follow_cli_spec tests/test_cli_contract.py::test_submit_success_fields_follow_cli_spec tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Aggregate Project/Observe Visibility Proof Mapping

Implemented:

- Reclassified the aggregate project/source/config/experiment/observe evidence rows as proved for current default/local paths now that their detailed rows have direct evidence.
- Reclassified the visibility model row as proved for current public, token, inspection, observe read, and annotation authorization surfaces.
- Kept release gates and top-level completion gates separate: full default-suite verification remains stale for the current worktree, and real Docker/network/service gates remain `ENV-GATED`.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials tests/test_cli_contract.py::test_inspection_context_help_capability_display_uses_inspection_token_and_explicit_credentials tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Current Worktree Full Default-Suite Gate

Implemented:

- Re-ran the default closeout gate after the source-import/tree-hash code/test changes and documentation proof-mapping batches.
- Reclassified the full default-suite gate as proved for the current worktree.
- Kept real Docker/network/service gates as explicit `ENV-GATED` release validation.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/source_import.py tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.
- Post-record docs sanity: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Documentation Consistency Closeout

Implemented:

- Ran the final documentation consistency pass for the current documentation set.
- Reclassified the documentation consistency P0 gate and the documentation/milestone blueprint row as proved for current README/spec/progress/audit/local-note state.
- Reclassified the local-only product-scope row as proved for the current surface because the runtime-surface guard and manual documentation pass now cover the previously open docs/README consistency condition.
- Updated the ignored local `AGENTS_cn.md` note so it matches `AGENTS.md` on the split between dashboard, pipeline, closed gaps, historical log, and completion audit.
- Removed the final docs consistency pass from the active queue and added a closed guardrail.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_local_agent_notes_and_env_files_are_gitignored tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts tests/test_cli_contract.py::test_cli_primary_object_type_tables_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_conflict_option_contracts_are_synchronized tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_registered_command_success_field_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md AGENTS_cn.md` returned no matches.

## 2026-05-21 Runtime Stack And Typer Boundary Proof

Implemented:

- Added a Typer app boundary in `src/alab/cli.py` for the real console entrypoint while preserving the existing `cli.run(argv)` service-facing parser and command semantics.
- Disabled Typer's own help interception and configured it to pass arbitrary argv through so ALab's global pre-scan, context-aware help, and command preflight remain authoritative.
- Added `tests/test_cli_contract.py::test_runtime_stack_and_entrypoint_follow_blueprint_contract` to prove the pyproject stack contract, console-script entrypoint, uv package mode, Python/Ruff targets, runtime dependency roots, Typer/`sqlite3`/Pydantic imports, dynamic `tomli-w`/`pathspec` usage, Typer app delegation, and stable console help/error behavior.
- Reclassified the runtime stack and architecture audit row as proved for the current local/runtime stack and added a closed guardrail.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_runtime_stack_and_entrypoint_follow_blueprint_contract tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies tests/test_cli_contract.py::test_output_rich_is_single_command_and_non_persistent -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/cli.py tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run alab --help`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run alab not-a-command`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/cli.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Lifecycle Evidence Map Closeout

Implemented:

- Added `tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces`.
- Mapped every current registered archive/unarchive command and every current registered lifecycle hard-remove/cleanup remove command to direct runtime evidence, excluding immediate tag removal because it has no archive state.
- Reclassified the lifecycle direction and lifecycle remove/idempotency audit rows as proved for current registered default/local lifecycle surfaces.
- Added a closed guardrail so future batches update the evidence map instead of re-reading broad lifecycle smoke tests from scratch.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- Focused docs sanity: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- Full default suite: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- Full static checks: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`; `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`; `git diff --check`

## 2026-05-21 Home Filesystem And Path Registry Evidence Map

Implemented:

- Added `tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current`.
- Mapped home resolution/layout, path-registry hashing/reuse, context marker contracts/conflicts, and worktree/checkout/repair path evidence to exact tests.
- Reclassified the ALab home/filesystem layout, home resolution, and context marker/path-registry audit rows as proved for current default/local behavior.
- Marked the full default-suite gate stale because this batch changed tests and docs after the previous full-suite pass.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Final Default-Suite Closeout Gate

Validated:

- Re-ran the full default/local gate after the home/filesystem/path-registry evidence-map and host-support policy proof batches.
- Reclassified the P0 full default-suite gate as proved for the current worktree.
- Removed the full-suite rerun item from the active queue; future work should re-add it only after implementation/test changes or before a release claim.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md tests/test_cli_contract.py` returned no matches.

## 2026-05-22 Source And Runner Direction Evidence Maps

Implemented:

- Added `tests/test_cli_contract.py::test_source_public_experiment_evidence_map_refs_stay_current`.
- Added `tests/test_cli_contract.py::test_runner_adapter_evidence_map_refs_stay_current`.
- Reclassified the source/public experiment direction row as proved for current default/local paths.
- Reclassified the runner/adapter direction row as proved for default/fake paths while keeping real Docker/network/native dependency gates `ENV-GATED`.
- Updated the dashboard, pipeline, and closed-gap guardrails so future work does not reopen these broad families without a named edge.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_source_public_experiment_evidence_map_refs_stay_current tests/test_cli_contract.py::test_runner_adapter_evidence_map_refs_stay_current tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Core Successful Workflow Closeout

Implemented:

- Reclassified the top-level core successful workflow row as proved for the current default/local/fake-adapter workflow.
- Tied that closeout to the already-proved public/private collaboration rows, adapter-derived source rows, lifecycle rows, runner/adapter rows, and 2026-05-22 full default-suite rerun.
- Updated the dashboard, pipeline, and closed-gap guardrails so future agents do not reopen the broad core workflow proof without a named audit edge.

Validation:

- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Observe Collaboration Audit Wording Refresh

Implemented:

- Replaced stale observe/collaboration intro wording that still said most rows were `PARTIAL`; the table rows are now proved for current default/local surfaces.

Validation:

- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Storage Audit Object Evidence Map

Implemented:

- Added `tests/test_cli_contract.py::test_storage_audit_object_evidence_map_refs_stay_current`.
- Mapped schema/index/JSON contracts, maintenance/catalog audit metadata, credential/token/context audit metadata, lifecycle retained-row/trash relationships, and annotation/visibility audit relationships to exact tests.
- Reclassified the core object model, SQLite retained-row relationship, and audit event retention rows as proved for current default/local object families.
- Updated dashboard, pipeline, and closed-gap guardrails so this storage/audit/object proof family is not reopened without a named edge.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_storage_audit_object_evidence_map_refs_stay_current -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_storage_audit_object_evidence_map_refs_stay_current tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Capability Help And Payload Preflight Closeout

Implemented:

- Reclassified the context-aware help/capability preflight rows as proved for current generated/default/context surfaces.
- Reclassified the file/output payload preflight row as proved for current text payload readers, stdin/file conflicts, output parent checks, and `OUTPUT_EXISTS` behavior.
- Updated the dashboard, pipeline, and closed-gap guardrails so these preflight families stay closed unless a new registered command, context mode, credential surface, or payload option changes the matrix.

Validation:

- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Real Docker-Backed Gate Closeout

Implemented:

- Fixed the opt-in real Docker CLI workflow test to expect the current `project init` warning field for hidden Docker setup output.
- Reclassified the real Docker-backed subset as proved on the current Darwin/Docker Desktop host: Docker runner, Dockerfile cache, CLI Docker workflow, Harbor verifier variants, and SkyDiscover Docker evaluator.
- Kept live SkyDiscover catalog and SkyDiscover Python local-wheel/network/native dependency gates explicitly `ENV-GATED`.
- Updated the dashboard, pipeline, audit, and closed-gap guardrails so future work does not reopen the real Docker-backed subset without a host/platform change.

Validation:

- `ALAB_RUN_REAL_DOCKER=1 UV_LOCKED=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_cli_project_run_workflow -q`
- `ALAB_RUN_REAL_DOCKER=1 UV_LOCKED=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -m real_docker -q`
- Full default-suite/static checks are recorded in the P0 completion gate for this same closeout batch.

## 2026-05-22 SkyDiscover Python Dependency Gate Closeout

Implemented:

- Reclassified SkyDiscover Python local-wheel/cache, networked dependency, and native dependency opt-in gates as proved on the current Darwin host.
- Confirmed the live SkyDiscover catalog gate is still environment-gated because this environment cannot reach GitHub over SSL, not because of an ALab implementation failure.
- Updated audit, dashboard, pipeline, and guardrails so the only remaining real-environment runner gate is live SkyDiscover catalog reachability.

Validation:

- `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -m real_skydiscover_python -q` (`1 passed, 3 skipped`)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_DEFAULT_INDEX=https://pypi.org/simple pytest -m networked_skydiscover_python -q` (`2 passed`)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_DEFAULT_INDEX=https://pypi.org/simple pytest -m native_skydiscover_python -q` (`1 passed`)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 pytest -m live_skydiscover_catalog -q -rs` skipped because GitHub returned `LibreSSL SSL_connect: SSL_ERROR_SYSCALL`.
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Real Docker Capability Refresh Gate Closeout

Implemented:

- Added an opt-in real Docker `config validate --refresh-capabilities` test that requires a reachable daemon, verifies rendered capability rows, and checks persisted Docker availability, Linux platform, architecture, CPU, and memory resource rows.
- Reclassified the global config real Docker refresh row as proved for the current Darwin/Docker Desktop host while keeping different release-target Docker daemons opt-in.
- Updated audit, dashboard, pipeline, and guardrails so future work does not reopen current real Docker capability refresh without a host/platform/Docker-version change.

Validation:

- `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_real_docker.py::test_real_docker_config_validate_refreshes_capability_cache -q`
- `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -m real_docker -q` (`10 passed`)
- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_real_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 CLI Audit Summary Closeout

Implemented:

- Added `tests/test_cli_contract.py::test_completion_audit_cli_evidence_rows_are_not_stale` so the P0 CLI gate, product CLI/output row, CLI summary row, and decomposed CLI long-tail rows cannot contradict each other.
- Reclassified CLI golden/command-contract completeness as proved for current registered CLI surfaces because the decomposed CLI long-tail rows now cover parser, renderer, capability, success-schema, saved result-failure, system-error, error/warning catalog, payload, and documentation-contract evidence.
- Updated dashboard, pipeline, and guardrails so future work does not reopen CLI golden/command-contract completion without a named command/output change.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_completion_audit_cli_evidence_rows_are_not_stale tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Live SkyDiscover Catalog Gate Closeout

Implemented:

- Re-ran the opt-in live SkyDiscover catalog marker in the current network environment; it passed instead of skipping.
- Reclassified current live SkyDiscover catalog and real-environment runner rows as proved for the current Darwin host, alongside the already proved real Docker-backed and SkyDiscover Python dependency gates.
- Updated the dashboard, pipeline, completion audit, and closed-gap guardrails so the active queue now only tracks grouped blueprint/subsystem audit-row decomposition. Release-target host, platform, Docker, Python dependency, or upstream SkyDiscover catalog changes still require rerunning the relevant opt-in gates.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 pytest -m live_skydiscover_catalog -q -rs` (`1 passed`)
- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Final Requirement Ledger Closeout

Implemented:

- Reclassified the top-level blueprint/subsystem requirement audit gate as proved for the current V1 evidence ledger after confirming no active `PARTIAL`, `PENDING`, or `ENV-GATED` requirement rows remain outside status legend and future-state instructions.
- Cleared the active pipeline queue for the current worktree and updated the dashboard/closed-gap guardrails to treat future work as newly scoped changes rather than inherited backlog.
- Kept release-target real-environment reruns conditional on host/platform/Python/network/upstream behavior changes.

Validation:

- ``rg -n '^\| .* \| `PARTIAL`|^\| .* \| `PENDING`|^\| .* \| `ENV-GATED`' docs/completion_audit.md docs/completion_audit_cn.md`` returned no active requirement-row matches.
- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-22 Examples and Agent Isolation Batch

Implemented:

- Hardened the SkyDiscover Codex example so controller and worker launches use narrow workspaces instead of the repository root or the whole `.run/` tree; project keys now live under ignored `.run/secrets/`, while workers receive only the experiment worktree plus non-secret ALab home/cache/shared writable directories.
- Added four examples: `local_agent_scoreboard`, `docker_file_reward_artifacts`, `harbor_verifier_minimal`, and `collaboration_observe_lifecycle`; added the top-level examples matrix in English and Chinese.
- Added the Chinese-only root practice note `潜在问题.md` with an explicit markdown-pair test exception, and captured real-run observations for Codex state writes, Docker buildx state writes, `workspace-write` read/write boundaries, network instability, and uv index requirements.
- Updated README/README_cn and the experiment-worker, project-controller, and global-admin skills and command references with the narrowed worker launch pattern and secret-surface rules.
- Added contract tests for the examples matrix, the Chinese-only note exception, and Codex launch isolation fragments.

Validation:

- `bash -n examples/*/scripts/*.sh`
- Dry-run checks for all five examples.
- End-to-end local runs for `local_agent_scoreboard` and `collaboration_observe_lifecycle`.
- Real Docker runs for `docker_file_reward_artifacts` and `harbor_verifier_minimal` on Docker Desktop `29.2.1 linux/arm64`; these required elevated execution because Docker buildx writes host `~/.docker/buildx/activity`.
- Real SkyDiscover setup, one real Codex worker, ALab evaluation, and report collection for `skydiscover_circle_packing_codex`; controller multi-worker execution was not run because the single worker already proved the path and consumed substantial Codex resources.
- Focused example/docs contract tests: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_chinese_only_potential_issues_note_is_the_only_markdown_pair_exception tests/test_cli_contract.py::test_examples_matrix_paths_exist_and_document_current_examples tests/test_cli_contract.py::test_example_codex_launches_use_narrow_worktree_sandboxes tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`

## 2026-05-23 Complete Examples Expansion

Implemented:

- Expanded `docker_file_reward_artifacts` from a constant-score Docker example into a containerized clinic-order fulfillment planner with order and warehouse data, cold-chain and priority constraints, manifest/summary/reward artifacts, and artifact export.
- Expanded `harbor_verifier_minimal` into a Harbor hidden-verifier incident urgency classifier. The editable starter exposes `score_ticket` and `classify_ticket`; private verifier cases now score the candidate and write numeric-only reward metrics.
- Expanded `collaboration_observe_lifecycle` into a two-stage incident triage collaboration demo: public step one changes queue order to severity-first, and step two continues from `best` with SLA balancing, runbook shortcuts, and security escalation.
- Added/updated README task descriptions and the examples matrix so each example has a distinct demo task, not just a feature checklist.
- Added `tests/test_cli_contract.py::test_examples_are_task_shaped_demos` to keep example task assets and README task sections from regressing.
- Updated role skills with the reward-file practice point learned from Harbor: reward JSON metrics must be finite numbers; detailed diagnostics belong in artifacts or logs.

Validation:

- Dry-run checks for all example scripts.
- `local_agent_scoreboard` setup and manual end-to-end run passed.
- `collaboration_observe_lifecycle` setup and end-to-end run passed; step one reward `0.821505`, step two reward `1.0`.
- `docker_file_reward_artifacts` real Docker setup and run passed on Docker Desktop; improved run reward `0.899235` and captured 3 artifacts.
- `harbor_verifier_minimal` real Harbor setup and run passed after moving non-numeric verifier details out of `reward.json`; improved run reward `0.92625`.
- Focused examples contract and ruff checks passed.

## 2026-05-23 Examples Follow-Up: Reward Diagnostics and Single-Worker Codex

Implemented:

- Tightened JSON reward parsing for file and Harbor rewards so reward files must be string-to-finite-number maps. Invalid JSON metric shapes now fail as reward parse errors before run records are stored, avoiding generic storage failures for user-authored reward files.
- Removed the SkyDiscover controller/multi-worker example path and kept the SkyDiscover demo focused on a single isolated Codex worker.
- Added Codex worker preflights for unsafe worktree paths and secret side directories, and clarified that added ALab home/cache/shared directories are CLI state rather than editable source.
- Propagated `UV_DEFAULT_INDEX=https://pypi.org/simple` through example scripts and README commands, and added local dependency troubleshooting for Docker, Harbor, SkyDiscover, Codex, and uv-backed flows.
- Updated runner specs, examples documentation, and role skills with numeric-only reward JSON guidance and source-vs-state worker boundary guidance.

Validation:

- `bash -n examples/*/scripts/*.sh`
- Dry-run checks for all example scripts.
- Focused reward parser and examples contract tests:
  `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_harbor.py::test_harbor_reward_parser_handles_json_text_missing_and_invalid_values tests/test_cli_contract.py::test_examples_are_task_shaped_demos tests/test_cli_contract.py::test_example_codex_launches_use_narrow_worktree_sandboxes tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_chinese_only_potential_issues_note_is_the_only_markdown_pair_exception -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`

## 2026-05-23 Full-Suite Evidence Sync

Implemented:

- Updated the P0 full default-suite evidence row to point at the latest 2026-05-23 post-examples/reward-parser full-suite run instead of the older 2026-05-22 CLI audit closeout run.
- Updated the dashboard and active-pipeline dates/current wording, plus synchronized Chinese counterparts.
- Clarified that this batch only adjusts documentation wording and does not add implementation or test changes, so the 2026-05-23 full-suite gate remains the latest implementation/test gate.

Validation:

- Focused docs sync: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-23 Docs Directory README

Implemented:

- Added [docs/README.md](README.md) as the documentation directory guide, covering default read order, document groups, and update rules.
- Added synchronized [docs/README_cn.md](README_cn.md).
- Updated the root README/README_cn repository tree and documentation section to point to the docs guide.

Validation:

- Focused docs sync and README structure tests: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" README.md README_cn.md docs/README.md docs/README_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md` returned no matches.

## 2026-05-23 TSP Template Library

Implemented:

- Added `examples/templates/` as a copyable default TSP template suite covering `tsp_local`, `tsp_docker`, `tsp_harbor`, `tsp_skydiscover_python`, and `tsp_skydiscover_docker`.
- Gave every template a complete project config or generated-config template, starter `solution.py`, deterministic city data, validation/evaluator logic, `scripts/setup_project.sh`, `scripts/run_demo.sh`, and ignored `.run/` state.
- Standardized the TSP contract around `build_route(cities) -> list[int]`, numeric-only reward metrics, deterministic 2-opt demo improvement, route artifacts/feedback, hidden Harbor verifier diagnostics, and local path injection for adapter templates.
- Updated root and examples README pairs with the template matrix and usage path.
- Aligned SkyDiscover adapter config preflight with runner resolution so local evaluator refs work without requiring a SkyDiscover catalog checkout.
- Added contract tests for template completeness, shell syntax, dry-run behavior, local SkyDiscover evaluator refs, default local/SkyDiscover Python template real runs from a temp copy, and opt-in real Docker template runs.
- Updated the completion audit SkyDiscover project-init row with the new local evaluator-ref evidence.

Validation:

- `bash -n examples/templates/scripts/check_templates.sh examples/templates/tsp_*/scripts/*.sh examples/templates/tsp_harbor/task/tests/test.sh examples/templates/tsp_skydiscover_docker/evaluator/evaluate.sh`
- `ALAB_REPO_ROOT=/Users/hobeter/Desktop/code/ALab examples/templates/scripts/check_templates.sh`
- Focused template/example contract tests: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_project_init_skydiscover_accepts_local_evaluator_ref_without_catalog tests/test_cli_contract.py::test_examples_matrix_paths_exist_and_document_current_examples tests/test_cli_contract.py::test_examples_are_task_shaped_demos tests/test_cli_contract.py::test_tsp_templates_are_complete_and_dry_run tests/test_cli_contract.py::test_tsp_local_and_skydiscover_python_templates_run_from_temp_copy tests/test_cli_contract.py::test_example_codex_launches_use_narrow_worktree_sandboxes tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- Full default suite: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- Real Docker gate: `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -m real_docker -q` (`11 passed`)
- All opt-in full suite: `ALAB_RUN_REAL_DOCKER=1 ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q -rs --junitxml=/private/tmp/alab-all-optin-pytest.xml` (JUnit `tests=389`, `skipped=0`, `failures=0`, `errors=0`)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check src tests examples/templates`
- `git diff --check`

## 2026-05-23 Multi-Instance TSP Template Hardening

Implemented:

- Replaced the single 12-city TSP dataset in every template with a deterministic 15-instance benchmark: five 100-city instances, five 500-city instances, and five 1000-city instances, for 8000 total cities.
- Changed all template reward policies to minimize `total_tour_length`, the sum of all per-instance closed-tour lengths, while keeping reward JSON metrics numeric-only and invalid routes penalized with large finite values.
- Tightened route validation to require actual non-bool integer indexes instead of coercing strings or floats into integers.
- Kept starter `solution.py` intentionally weak with `list(range(len(cities)))`; changed demo scripts to enable deterministic nearest-neighbor improvement instead of naive 2-opt so demos remain fast at the larger sizes.
- Added `examples/templates/reference_solution/solution.py` with deterministic multi-start nearest-neighbor plus bounded 2-opt, plus README/README_cn target documentation requiring `total_tour_length <= 2650000` while explicitly not claiming global optimality.
- Updated local/Docker validators, Harbor verifier, SkyDiscover Python evaluator, and SkyDiscover Docker evaluator to loop over the same multi-instance contract and emit route/details feedback outside reward JSON.
- Updated README pairs and contract tests to document and verify the 15-instance benchmark, minimize reward direction, baseline difficulty, and reference-solution target threshold.

Validation:

- `bash -n examples/templates/scripts/check_templates.sh examples/templates/tsp_*/scripts/*.sh examples/templates/tsp_harbor/task/tests/test.sh examples/templates/tsp_skydiscover_docker/evaluator/evaluate.sh`
- Direct local starter validation: `ALAB_RUN_DIR=/private/tmp/alab-tsp-template-direct python examples/templates/tsp_local/source/validate_tsp.py` (`total_tour_length=42000612.353972`, `valid=1`)
- Direct reference-solution validation through the local validator: `total_tour_length=2586654.146307`, `valid=1`
- `ALAB_REPO_ROOT=/Users/hobeter/Desktop/code/ALab examples/templates/scripts/check_templates.sh`
- Focused template/example contract tests: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_examples_matrix_paths_exist_and_document_current_examples tests/test_cli_contract.py::test_examples_are_task_shaped_demos tests/test_cli_contract.py::test_tsp_templates_are_complete_and_dry_run tests/test_cli_contract.py::test_tsp_reference_solution_meets_documented_threshold -q`
- Local/SkyDiscover Python template real runs from a temp copy: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_tsp_local_and_skydiscover_python_templates_run_from_temp_copy -q`
- Real Docker TSP template gate: `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_real_docker.py::test_real_docker_tsp_templates_run_from_temp_copy -q -rs`
- All opt-in full suite: `ALAB_RUN_REAL_DOCKER=1 ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q -rs --junitxml=/private/tmp/alab-all-optin-pytest.xml` (JUnit `tests=390`, `skipped=0`, `failures=0`, `errors=0`)
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check tests/test_cli_contract.py examples/templates`
- `git diff --check`

## 2026-05-23 TSP Template Usability Polish

Implemented:

- Added per-template README/README_cn files under each `examples/templates/tsp_*` directory so a single copied template keeps its local command path, editable-file map, runner requirements, and `.run/`/secret-state conventions.
- Updated the top-level template README pair to document the per-template README files and the `ALAB_REPO_ROOT`/`ALAB_BIN` path-quoting behavior.
- Reworked every TSP template setup/run script to build the default ALab command as a Bash array and to persist the generated command array in `.run/secrets/project.env`, so copied template paths and custom wrapper paths containing spaces are handled without breaking argument boundaries.
- Extended the template contract tests to require each local README pair and to run the default local/SkyDiscover Python template demo from a copied template path plus `ALAB_BIN` wrapper path containing spaces.

Validation:

- `bash -n examples/templates/scripts/check_templates.sh examples/templates/tsp_*/scripts/*.sh examples/templates/tsp_harbor/task/tests/test.sh examples/templates/tsp_skydiscover_docker/evaluator/evaluate.sh`
- `examples/templates/scripts/check_templates.sh`
- Focused template tests: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q tests/test_cli_contract.py::test_tsp_templates_are_complete_and_dry_run tests/test_cli_contract.py::test_tsp_reference_solution_meets_documented_threshold tests/test_cli_contract.py::test_tsp_local_and_skydiscover_python_templates_run_from_temp_copy`
- Real Docker TSP template gate: `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q -rs tests/test_real_docker.py::test_real_docker_tsp_templates_run_from_temp_copy`
- Full default suite: `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check tests/test_cli_contract.py examples/templates`
- `git diff --check`

## 2026-05-24 HOME Feedback Command

Implemented:

- Added top-level `alab feedback --body <text>|--body-file <path> [--kind suggestion|question|bug|other] [--title <text>]` as a submit-only initialized-HOME command available without key or token validation.
- Added canonical `ALAB_HOME/feedback/` storage with one atomic plaintext record directory per feedback item, containing `metadata.json` and `body.md`.
- Captured feedback metadata for role, actor/context/session, cwd, best-effort Git commit/dirty state, ALab home, and body path, using JSON `null` for missing values.
- Kept feedback available for initialized homes even when global config is invalid, matching the command's HOME-only precondition.
- Updated README, blueprint, CLI/storage specs, `.env.example`, role skills, progress, and completion-audit documents with synchronized Chinese versions.
- Added CLI contract tests for command registry/docs sync, role/context availability, no-token-file experiment context behavior, no-HOME behavior, metadata/body persistence, session priority, Git/non-Git metadata, body-file handling, and invalid input side-effect prevention.

Validation:

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py tests/test_smoke.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- `git diff --check`
