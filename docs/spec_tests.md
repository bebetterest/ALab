# ALab V1 Test Spec

This spec defines the required V1 verification plan. Tests should use project-local tooling and isolated temporary `ALAB_HOME` directories.

Implementation should establish CLI result schemas and text golden tests before broad service implementation, then add storage, service, integration, runner, and adapter tests against those stable outputs.

## 1. Golden CLI Tests

Add golden tests for every command's:

- Text success output.
- Text result-failure output.
- Text system-error output where applicable.
- Alias behavior.
- Global option placement.
- Every registered command and alias must have generated runtime coverage proving duplicate global options, missing or empty global option values, invalid `--output` values, and `--key`/`--key-stdin` conflicts fail with `CONFIG_INVALID` before home creation or command matching.
- Stable field labels and field ordering.
- Primary `object: <type>` values for every command and alias, including row object types for list/search results.
- Strict text object blocks beginning with `object: <type>`, blank-line object separation, indented multiline fields, and warnings rendered after primary results as `object: warning`.
- Lists render as repeated labeled lines, never as comma-separated scalar fields.
- Nullable `none`, literal user text `none`, and empty user text are distinct in text output; user-provided text renders through multiline fields.
- `--output rich` selecting the same result data without becoming persistent.
- Global options accepted before and after commands and aliases.
- Every registered command and alias must have generated runtime coverage proving trailing global `--home`, `--key`, and `--output text` are consumed by global pre-scan before handler option validation, without DB/config/marker/token/tree/worktree side effects on rejected commands.
- Global option pre-scan stops at standalone `--`; global-looking arguments after `--` are not treated as global options.
- Every registered non-help command and alias must have generated runtime coverage proving global-looking tokens after standalone `--` are not consumed by global pre-scan, do not read `--key-stdin`, do not switch the selected home, and leave rejected command DB/config/marker/token/tree/worktree state unchanged.
- Command-local options reject duplicates before writes, file exports, runner execution, or lifecycle audit rows unless the option is explicitly documented as repeated.
- Every registered command-local singleton option, including helper-backed lifecycle aliases, must have generated runtime coverage proving duplicate uses fail with `CONFIG_INVALID` before availability fallback, selector lookup, file reads, writes, runner execution, or lifecycle audit rows, with fresh DB/file/tree/export/worktree snapshots per command/option case.
- Global options requiring values reject absent values, empty string values, and option-looking `--...` next tokens before home creation or command matching.
- Command-local options requiring values reject absent values and option-looking `--...` next tokens before file reads, writes, runner execution, or lifecycle audit rows. Structural command-local values also reject empty string values before those side effects, while documented direct user-text fields keep empty string distinct from missing/null text when their field validators allow empty text.
- Every registered command-local value option must have generated runtime coverage proving absent values fail with `CONFIG_INVALID` before availability fallback, mutually exclusive relationship validation, file reads, writes, runner execution, or lifecycle audit rows, with fresh DB/file/tree/export/worktree snapshots per command/option case.
- Every registered command-local structural value option must have generated runtime coverage proving empty string values fail with `CONFIG_INVALID` before availability fallback, mutually exclusive relationship validation, file reads, writes, runner execution, or lifecycle audit rows, with fresh DB/file/tree/export/worktree snapshots per command/option case, while direct user-text empty handling remains covered by multiline/empty text rendering tests.
- Every registered non-help command must have generated runtime coverage proving unsupported command-local options fail with `CONFIG_INVALID` before handler payload parsing, selector lookup, file reads, writes, runner execution, lifecycle audit rows, or DB/config/marker/token/tree/worktree mutations.
- Every registered command using shared typed/structured value parsers for pagination, source limits, retention counts, object id filters, integer filters, numeric filters, boolean filters, sort fields, choice filters, or time filters must have generated runtime coverage proving malformed values fail with stable `CONFIG_INVALID` errors and no DB/config/marker/token/tree/export/worktree side effects, with fresh snapshots per command/option/value case.
- Project config/env/secret mutation conflicts such as `--dry-run` with `--skip-baseline-test` must fail with `CONFIG_INVALID` before config or secret payload file reads, validation writes, DB mutation, marker mutation, or runner execution, with fresh DB/file/tree snapshots per command case.
- Documented non-remove command conflicts, including source selectors, cache/backup selectors, token selectors, submit refs, and annotation body/target selectors, must have runtime coverage proving stable errors and no DB/config/marker/token/tree or payload-file side effects, with fresh DB/file/tree snapshots per conflict case.
- Every literal value-option read in service handlers, including reads performed through shared parsing helpers, must be registered in the central value-option table used by positional parsing and missing-value validation.
- Helper-mediated singleton value-option parsers must be included in the static duplicate-guard classification so their literal option arguments count as guarded command-local options.
- Every literal option read in a guarded service handler, including helper-mediated reads for pagination, sorting, source selection, mutable/visibility policy, credential selectors, typed filters, and time filters, must appear in that handler's known-option allowlist.
- Every registered command handler must validate positional arguments through the shared fixed-count or optional-selector helpers, directly or through a documented lifecycle helper.
- Every registered zero-positional command must have generated runtime coverage proving an extra positional argument fails with `CONFIG_INVALID` before DB/config/marker/token changes, file exports, source staging, runner execution, or lifecycle audit rows, with fresh DB/file/tree snapshots per command.
- Every registered single-selector command, including helper-backed observe and annotation lifecycle aliases, must have generated runtime coverage proving surplus positional arguments fail with `CONFIG_INVALID` before selector lookup, file exports, token/path mutation, or lifecycle audit rows, with fresh DB/file/tree snapshots per command.
- Every registered required single-selector command must have generated runtime coverage proving missing selectors fail with the stable object-specific `*_NOT_FOUND` code before DB/config/marker/token changes, file exports, checkout creation, source staging, runner execution, or lifecycle audit rows, with fresh DB/file/tree snapshots per command.
- Every registered fixed-count positional command must have generated runtime coverage proving surplus positional arguments fail with `CONFIG_INVALID` before config writes, project/source initialization, secret file reads, config-version writes, tag mutation, or lifecycle audit rows, with fresh DB/file/tree snapshots per command.
- Every registered fixed-count positional command must also have generated runtime coverage proving missing required positional arguments fail with `CONFIG_INVALID` before config writes, project/source initialization, secret file reads, config-version writes, tag mutation, or lifecycle audit rows, with fresh DB/file/tree snapshots per command.
- `--key` and `--key-stdin` mutual exclusion.
- `--key-stdin`, `project secret set --value-stdin`, and `project secret set --value-file` reject empty values, embedded newlines, and NUL bytes after stripping at most one trailing newline.
- Empty ambient `ALAB_KEY` behaves like an absent key and must not turn missing-credential failures into `AUTH_DENIED`.
- Full ALab object ids required for object selectors, with only Git commit SHA selectors accepting unambiguous abbreviations.
- RFC 3339 timestamp parsing with required `Z` or numeric offset for all time filters.
- Command error matrix coverage for every documented command family.
- Fixed stable error-code to numeric-exit mapping, including `PROJECT_INVALID` exit `4`, all `*_NOT_FOUND` exit `2`, and saved runner/validation `error` records exiting `1`.
- Object-specific not-found codes for run, validation, artifact, log, annotation, credential, audit, catalog, and cache selectors.
- `ALAB_DEBUG=1` stack trace behavior for internal errors without locals/env/secrets/hidden contents.
- README and README_cn opt-in pytest marker commands must stay synchronized with `pyproject.toml` pytest marker declarations and actual marker use under `tests/`.
- Every Markdown file in the repository root and `docs/` must keep a synchronized Chinese `*_cn.md` pair, and every `*_cn.md` file in those locations must have an English source file.
- README and README_cn repository structure trees must stay synchronized and every listed path must exist.
- `.gitignore` must keep local agent notes (`AGENTS*.md`, `CORE*.md`) and real environment files (`.env`, `.env.*`) ignored while keeping `.env.example` trackable.
- `.env.example` must exist and cover the environment variable assignments documented by both README setup sections, plus the core ALab/uv/debug knobs used by local and opt-in validation workflows.
- Context-aware capability help for no-command `alab`, `alab help`, `alab --help`, and nested command help requests.
- Dynamic help output in global, project, experiment, and inspection contexts.
- Invalid global config blocks normal command and help execution with `CONFIG_INVALID`, while `auth init` and `config show|set|reset|validate` remain available for diagnosis or repair.
- Invalid global config takes precedence over explicit credential lookup for non-repair commands, so a bad `--key` cannot mask a broken `config.toml`.
- Unparseable global config TOML prevents `config set` and field-level `config reset` from rewriting the file; only `config reset --all` may restore the default config.
- Default help hiding locked commands, and `alab help --all --explain` rendering safe `help_command` rows with locked reasons, unlock hints, context type, credential source, and capability source.
- Explicit `--key` and `--key-stdin` unlocking project-admin or root surfaces, while ambient `ALAB_KEY` does not affect help output or broaden token/public command surfaces.
- Explicit root/admin credential surfaces must have generated runtime coverage proving registered commands outside the credential surface, including token-only commands outside experiment worktree contexts and root-only commands under admin keys, fail with `COMMAND_UNAVAILABLE` before handler option parsing, file reads, file/output writes, DB mutation, marker/token mutation, Git operations, runner execution, or filesystem staging, with fresh DB/file/tree snapshots per command/payload variant.
- Root-only long-running dashboard coverage must prove no-key, admin, token, and public contexts cannot enter the server; invalid port/refresh values fail before bind; `--no-open` avoids browser launch in tests; startup output is flushed before serving; and clean shutdown exits `0`.
- Invalid explicit credentials through `--key` and `--key-stdin` must have generated registered-command coverage proving `AUTH_DENIED` occurs before handler option parsing, unsupported-option validation, config/body/value/summary/feedback file reads, output parent creation, DB mutation, config/marker/token mutation, or project/source/tmp tree changes, with a fresh snapshot for each command variant.
- Direct invocation of commands outside the current capability surface failing with `COMMAND_UNAVAILABLE` exit `4` before reading body/value files, writing SQLite rows, creating audit events, running Git, or executing runners.
- Public project contexts must have generated runtime coverage proving every registered command outside the public project surface fails with `COMMAND_UNAVAILABLE` before handler option parsing, file reads, file/output writes, DB mutation, marker/token mutation, Git operations, runner execution, or filesystem staging; each unsupported option, missing file, config-file, and output-path payload must use a fresh SQLite/file/tree snapshot.
- Experiment-token contexts must have generated runtime coverage proving every registered command outside the worktree-token surface fails with `COMMAND_UNAVAILABLE` before handler option parsing, file reads, file/output writes, DB mutation, marker/token mutation, Git operations, runner execution, or filesystem staging; each payload must use a fresh SQLite/file/tree/worktree snapshot.
- Inspection-token contexts must have generated runtime coverage proving every registered command outside the inspection surface fails with `COMMAND_UNAVAILABLE` before handler option parsing, file reads, file/output writes, DB mutation, marker/token mutation, Git operations, runner execution, or filesystem staging; each payload must use a fresh SQLite/file/tree/checkout snapshot.

Commands covered:

- `help`, no-command `alab`, `alab --help`, and nested command help.
- `auth init`, `auth root regenerate`.
- `config show`, `config set`, `config reset`, `config validate`.
- `dashboard`.
- `key create`, `key list`, `key revoke`.
- `context show`, `context repair`.
- `project list/show/archive/unarchive/remove/status/init/config/env/secret/validate/validation/locks`.
- `source import/list/show/archive/unarchive/remove`.
- `catalog skydiscover add/update/show/remove`.
- `cache prune`, including `--trash --older-than`, `--trash-all`, and top-level `--all`.
- `backup prune`.
- `audit list`, `audit show`.
- `project secret gc`.
- `exp create/archive/unarchive/remove/checkout/worktree/token/tag`.
- `run`, `submit`.
- `observe experiments/runs/artifacts/logs/annotations`, including runs/artifacts/logs archive, unarchive, and remove.
- top-level aliases `status`, `exp`, `runs`, `artifacts`, `logs`, `annotations`.
- `annotate add/edit/archive/unarchive/remove`.

Lifecycle golden cases:

- Every actual hard remove command rejects missing `--force`, missing `--confirm`, wrong confirm id, and unarchived targets without DB/file/tree/trash side effects, with fresh snapshots per command and confirmation variant.
- Every hard remove command supports `--dry-run` that renders blockers and deletion counts without writing audit rows or deleting data, including a `target_not_archived` blocker with exit `0` when the target is not archived; dry-run coverage must prove fresh per-command DB/file/tree/trash snapshots remain unchanged.
- Every `--cascade` command fails with a stable blocker list when any dependent authoritative object is still active, and dependency-blocker coverage must prove DB/file/tree/trash and source Git refs remain unchanged per command.
- Archive and unarchive commands are idempotent, return success for already-matching state, and do not write duplicate audit rows.
- Error matrix cases confirm repeated archive/unarchive operations never return `PROJECT_ARCHIVED`, `EXPERIMENT_ARCHIVED`, or any already-archived failure code.
- `HOME_EXISTS` and `OUTPUT_EXISTS` render stable text errors.
- Public or optionally authorized commands ignore ambient `ALAB_KEY` for privilege elevation and render authorized details only with explicit `--key` or `--key-stdin`.
- Ambient `ALAB_KEY` may satisfy authentication only for commands already available in the current context surface; it never expands default help, public project surfaces, experiment token surfaces, or inspection token surfaces.
- Public project status coverage proves invalid projects render the reduced public-invalid field set under no key, ambient `ALAB_KEY`, and explicit non-admin credentials that are admitted through the public surface.
- Global explicit project admin key help shows same-project admin commands that can run with that project id explicitly; it does not show root-only cache, catalog, backup, global audit, or project creation capabilities.
- Experiment token help hides project config, project init, source management, experiment remove, worktree maintenance, cache, catalog, backup, audit, and key-management commands.
- Inspection token help hides run, submit, tag mutation, annotation mutation, project/source/config management, experiment mutation, worktree maintenance, cache, catalog, backup, audit, and key-management commands.
- Project no-key help shows public safe status and public experiment/source bootstrap only when project policy permits it.
- Public experiment creation coverage proves a valid but nonmatching explicit credential follows the public surface when policy permits it, while `project.allow_public_exp_create = false` hides and preflight-blocks public `exp create` without side effects.
- Explicit admin/root keys in an experiment or inspection path unlock matching same-project capabilities, but explicit `--project` for a different active context still fails with `CONTEXT_CONFLICT`.
- Token/public selectors for objects that exist outside the caller's visibility return non-disclosing `SCOPE_VIOLATION` rather than revealing object existence.
- `exp archive` rejects removed V1 flags `--remove-worktree` and `--force-remove-worktree`.
- Archived artifact/log export fails without `--include-archived`; archived artifact/log show by id succeeds when authorized.
- Config, artifact, and log exports fail with `OUTPUT_EXISTS` when the target exists and `--overwrite` is omitted.

Dashboard security cases:

- `alab dashboard` binds only to `127.0.0.1`, generates a random browser token in the URL fragment, and requires `X-ALab-Dashboard-Token` on every `/api/*` request.
- Missing or wrong API tokens return `401`; unknown routes return `404`; non-GET/HEAD methods return `405` and do not mutate state.
- API responses and frontend assets never expose raw root/admin keys, raw experiment tokens, credential verifier material, salts, or raw `secret_env` values.
- Root dashboard sessions can read hidden log full text and raw artifact/log download bytes through path-contained file reads.
- Static assets avoid inline event handlers and remain compatible with the dashboard CSP.

## 2. Storage And Migration Tests

Cover:

- DDL constraints and enum checks.
- Public id suffixes use 22-character unpadded base64url strings with 128 bits of entropy.
- Required nullable fields for running/error/interrupted run records.
- Required indexes used by project, experiment, run, source, artifact, log, annotation, credential, registry, and lock queries.
- WAL mode setup.
- SQLite backup API backup before migrations.
- Migration ordering and checksum recording.
- Global migration lock behavior.
- Downgrade rejection.
- Canonical JSON ordering and hash stability.
- Credential verifier storage without raw root/admin/token secrets.
- Raw root/admin/token credentials include the credential id in the raw wire format, but authorization still requires matching scope, active status, token mode/path where applicable, and salted HMAC verifier.
- Plaintext local `secret_env` storage in `secret_values`, with project-scoped HMAC fingerprints generated from the non-exported project fingerprint key.
- One active root key partial uniqueness.
- Admin key project scoping.
- Token mode and active worktree token uniqueness.
- `home_id` creation and context marker matching.
- Path registry realpath hashing.
- Path hashes use `sha256:<hex>` over normalized resolved realpaths.
- Secret value storage, HMAC fingerprints, retain markers, unset behavior, and GC candidate calculation.
- Secret HMAC fingerprints bind the `secret_env` name and value, and retain markers cannot be reused under a different name.
- Secret value rejection for empty, NUL-containing, and shorter-than-4-byte values.
- Config edits based on latest attempted config.
- Config edits skip continuous no-op configs, create monotonic versions when reverting to older content, and do not enforce unique config hashes.
- Metadata-only config edits create active `inherited` versions when the current runtime config is valid, with `active_validation_id` still pointing to the validation proving the unchanged runtime config.
- Metadata-only config edits not validating invalid runtime config.
- Config export default failing if target exists and succeeding with `--overwrite`.
- `project secret gc` requires exactly one of `--dry-run` or `--apply`; dry-run writes no audit row and apply deletes only unreferenced raw secret values.
- Lifecycle DDL columns and checks for project/source/experiment `pre_archive_status`, experiment `worktree_state`, run/validation/artifact/log `archive_status`, final run removed metadata, and path registry `removed` state plus removed metadata.
- DDL coverage for `experiment_tags`, `experiment_submissions`, `runtime_capabilities`, `catalogs`, `cache_entries`, `projects.secret_fingerprint_key`, `experiments.bound_validation_id`, `annotations.target_json`, and explicit validation archive columns.
- Retained `audit_events`, revoked `credentials`, removed `path_registry` rows, and cache/catalog metadata survive hard removal without broken foreign keys to deleted authoritative rows.
- Strict versioned JSON contracts for metadata, policy, record, target, visibility, origin, audit, and submission refs JSON.
- `audit_events` columns, generic action/object_type enum constraints, JSON metadata constraints, and event creation for hard remove, cache/catalog/backup prune, lock clear, and final run deletion.
- Migration uses an ALAB_HOME-level file lock; project and experiment operations use the SQLite `locks` table.
- Migration file naming, checksum validation, SQLite-backup-before-migration, per-version transaction rollback, home-level migration lock behavior including configured timeout to `RESOURCE_BUSY`, and checksum mismatch rejection.
- Global config defaults, SQLite busy-timeout application, invalid config repair-only command behavior, field-level repair, `reset --all`, and `validate --refresh-capabilities` for Docker availability/platform/resource probes.
- Audit list/show authorization and sanitized metadata rendering.
- Path registry `status='removed'` rows do not block path reuse but remain queryable for audit.
- `path_registry_id` is the primary key, active `path_hash` is unique, removed rows do not block path reuse, and reusing a path creates a new registry row.
- Full key-level JSON contracts reject unknown keys and enforce safe/public/token-renderable field boundaries.
- Context conflict when explicit `--project` disagrees with the current active ALab context.
- Context path nesting allows only same-project experiment or inspection contexts under that project's marker-only project control context; cross-project nesting and any nesting under experiment/inspection contexts are rejected.
- Marker/registry disagreement fails closed during normal command execution and can only be repaired through explicit `context repair` authorization or strict self-repair.
- Capability lookup is read-only, uses the same context detection result as command execution, and fails closed on marker/registry disagreement without auto-repair.
- Capability resolver decisions are identical for help rendering and command preflight for the same argv, context, and explicit credential.
- Path hashing applies platform case normalization on case-insensitive filesystems.

## 3. Auth, Context, And Lifecycle Tests

Cover:

- `auth init` creates home and displays generated root key once.
- `auth init` succeeds for a missing or empty home directory and fails with `HOME_EXISTS` for initialized or non-empty unrelated directories.
- Root key regeneration replaces the root key and revokes previous verifier.
- Lost-root unrecoverability.
- Project admin key create/list/revoke root-only behavior.
- Experiment token list metadata without raw tokens or verifier hashes.
- Token regeneration writes to registered `.alab/token` and never prints raw token.
- Token file is one raw token line and is ignored by Git.
- Experiment and inspection worktree creation writes worktree-local Git exclude rules for `.alab/`, and ALab staging always excludes `.alab/**`.
- Token file permission warnings.
- Context marker parsing.
- `context show` marker/registry output.
- Context conflict detection.
- `context repair` under root/admin.
- Strict token self-repair for moved experiment/inspection paths.
- Copied token self-repair blocked unless strict conditions hold.
- Project archive/unarchive restoring pre-archive status.
- Experiment archive/unarchive restoring pre-archive status.
- Source archive/unarchive constraints, including active default source block.
- Project/source/experiment hard remove requires archived state, correct confirmation, and allowed cascade dependencies.
- Filesystem hard remove moves ALab-owned paths into `tmp/trash/<audit_id>/`, immediately attempts deletion, records residual trash path on failure, and supports `cache prune --trash --older-than` and `cache prune --trash-all`.
- Filesystem hard remove uses same-parent `.alab-trash-<audit_id>` fallback for cross-device moves and best-effort restores the original path if audit/DB transaction fails after the trash move.
- Expired locks are automatically replaced during lock acquisition; `locks clear-stale` remains diagnostic.
- Lifecycle audit rows are created for archive, unarchive, remove, restore, repair, revoke, regenerate, prune, gc, catalog remove, worktree remove/restore, and checkout remove.
- Project remove is root-only, requires `--cascade`, deletes the project DB tree and filesystem state, and retains revoked credential rows for audit.
- Source remove always fails when any project config version references the source; otherwise it defaults to failing when active experiments depend on it, and `--cascade` succeeds only when dependent experiments are archived.
- Experiment remove deletes branch/worktree/inspection contexts, removes dependent run/log/artifact/annotation/tag records according to cascade rules, and revokes tokens.
- Run lifecycle supports archive/unarchive by own worktree token, root, and admin.
- Run remove is root/admin-only, requires archived run, recomputes `latest_run_id`, and preserves closed experiment final metadata when removing `final_run_id`.
- Project validation archive/remove is root/admin-only and blocked for the active validation proving `active_valid_config_version`.
- Worktree remove can run for open, closed, or archived experiments, supports `--dry-run`, requires root/admin plus `--force --confirm <exp_id>` for actual deletion, records dirty discard behavior, trash-stages filesystem deletion, revokes the active worktree token, marks the path registry row `removed`, and sets `worktree_state='removed'`.
- Worktree remove reconciles state and writes audit when the registered filesystem path is already missing.
- Run and submit reject experiments whose `worktree_state` is `removed`.
- Worktree restore requires `--path`, requires an empty or nonexistent destination, checks out branch HEAD, writes `.alab/context.json`, creates a new token, writes `.alab/token`, and sets `worktree_state='active'`.
- Inspection checkout remove supports `--dry-run`, deletes the inspection worktree through trash staging on actual deletion, reconciles state when the registered path is already missing, revokes its token, marks the path registry row removed, and has no restore command.

## 4. Project And Source Tests

Cover:

- Project init from local path, remote Git fixture, empty source, Harbor fixture, and SkyDiscover fixture.
- Project init requires `--config` for all runner types and rejects runner/reward/artifact/log/env runtime flags.
- Harbor and SkyDiscover project init reject `--source-ref`; explicit adapter init editable sources must be path, Git, or empty sources.
- Project init stages filesystem state before DB commit, writes project/source/config/admin credential rows in one transaction, and prints the admin key only after the transaction succeeds.
- Project init accepts configs without `source.default_source_ref` only when exactly one effective default source origin is supplied, then stores the canonical injected source ref.
- Project init fails with `CONFIG_INVALID` when an input `source.default_source_ref` does not match the staged canonical source ref.
- Adapter init dedupes identical explicit and adapter-derived sources and fails with a stable source conflict when their canonical tree hashes differ.
- Baseline pass creates valid project.
- Baseline fail creates invalid project and retains project/source/config/validation/log/artifact records.
- `--skip-baseline-test` writes config and marks invalid.
- `project validate` restores valid status.
- Invalid project blocks new `exp create`.
- Existing experiments continue to run and submit with their bound valid config version after project invalidation.
- Experiments store `bound_validation_id` at creation.
- Archived projects, sources, and experiments are hidden by default and visible with explicit include flags where defined.
- Closed experiments remain closed after unarchive.
- Project init always creates one admin key when the project record is written and prints it exactly once, including when baseline later fails and the project is retained invalid.
- Public safe status rendering.
- Public no-key project context cannot observe/show/config.
- Public projects allow no-key experiment creation from allowed sources and visible experiments.
- Public no-key `--from-exp` accepts `final`, `latest`, `best`, and reachable SHA selectors for open/closed experiments visible through the intersection of current project public policy and the source experiment's stored visibility upper bound.
- Public no-key `--from-exp` cannot inherit from an experiment that current project public policy lists but the source experiment's stored visibility upper bound excludes.
- Public no-key `--from-exp` rejects archived source experiments unless root/admin is supplied.
- Public no-key checkout/observe history is rejected.
- Public remote Git import controlled by `[public_source_import]`.
- Public remote Git import renders `PUBLIC_GIT_CREDENTIAL_HELPER_USED` when local non-interactive Git credential helpers may be used, and prompts remain disabled.
- `project config show/export` default to `--version latest-attempted`, support `--version active-valid|<n>`, and fail `active-valid` with `PROJECT_INVALID` when no active valid config exists.
- `project config import/set --dry-run` does not write DB rows, mutate files, create audit rows, or execute baseline runners.
- Project config/env/secret mutations do not write lifecycle audit rows; config versions and secret rows are authoritative. `project secret gc --apply` remains audited.
- `public_source_import.*` changes do not trigger baseline validation.
- Public source limits default to source limits and can be configured without a hard-coded cap.
- Default experiment worktree path is `./<project_id>_<exp_id>` relative to command cwd; the ALab home layout has no default `workspaces/` tree.
- Project control context lives at `project-workspaces/<project_id>/.alab/context.json` and is marker-only.
- Git submodule/gitlink source entries fail with `SOURCE_INVALID` and a next action to vendor or expand submodule content.
- Environment variable names in `[env]` and `[secret_env]` must match `^[A-Za-z_][A-Za-z0-9_]*$`.
- `project config set` replaces whole map/array fields and does not deep-merge.
- Private project requires root/admin for experiment creation.
- Source import local filesystem snapshot includes uncommitted unignored files.
- Source import excludes untracked sensitive files.
- Source import from inside a Git worktree applies `.alabignore` only to untracked files; tracked files remain imported and may emit tracked-sensitive warnings.
- Tracked sensitive source files emit warnings.
- Remote Git imports use `--git-ref`.
- Existing ALab source selection uses `--source-ref`.
- Source name auto-derivation when omitted.
- Empty-after-filter warnings.
- Subdir handling.
- Content hash dedupe returning existing source.
- Canonical source tree hash uses `alab-tree-sha256-v1` and is independent of Git object hash format.
- Source dedupe appends stable sanitized `origin_metadata_json.origins` entries without creating a new source ref.
- Archived sources are ignored for source dedupe.
- Source name slug uniqueness.
- Limit enforcement.

## 5. Run And Submit Tests

Cover:

- Experiment create at default and custom paths.
- Experiment name slug conflicts fail with `NAME_CONFLICT` for all callers, including public no-key callers.
- Default experiment path is `./<project_id>_<exp_id>`, fails if it exists, and may be created from any command cwd that passes path and nesting checks; a project control context is allowed but not required.
- Custom experiment path rejects any existing entry.
- Experiment mutable and visibility override can narrow but cannot expand.
- Same-project experiment and inspection contexts may be created under the marker-only project control context; different-project children and children under experiment/inspection contexts are rejected.
- Experiment mutable override is enforced as an intersection with the bound project mutable policy at run/submit time.
- Experiment visibility override is normalized to the intersection with current project visibility at creation and stored as the experiment upper bound.
- Mutable patterns use pathspec GitWildMatchPattern semantics, and rename/copy scope validation requires both source and destination paths to be allowed.
- `alab status` in experiment and inspection contexts.
- Run with changes creates commit.
- `running` run record is written before ALab auto commit.
- Run-created commit uses `ALab run: <message>` and ALab trailers.
- Full-diff scope failure after ALab auto commit rolls back only that auto commit, preserves file changes, and stores rolled-back commit hash and explanation.
- Auto-commit rollback leaves file changes unstaged.
- Full-diff scope failure caused by an existing manual commit records run `error`, returns actionable `SCOPE_VIOLATION` details, and leaves HEAD/worktree unchanged.
- Run on manual commit is accepted when full diff is in mutable scope.
- Run with valid manual commits plus dirty worktree changes validates the current manual full diff, auto-commits dirty changes, and then repeats full-diff mutable scope checking.
- Run rejects invalid Git states and out-of-scope changes.
- Existing staged changes are included.
- Run auto commit includes all mutable-allowed staged, unstaged, deleted, renamed, copied, and untracked non-ignored changes.
- Empty-change run creates no commit and stores a run record.
- Same commit can have multiple run records.
- Stale `running` run records become `interrupted`.
- Failed run stores logs, artifacts, and parsed reward if available.
- Run and submit require `experiments.worktree_state = 'active'`.
- Submit rejects archived projects even when the experiment is still open and the worktree is active.
- Submit accepts summary/feedback text or file only.
- Submit summary/feedback files resolve relative to current cwd.
- Submit stdin options are rejected.
- Submit refs are deduplicated preserving first-seen order.
- Submit stores exactly one `experiment_submissions` row only after a passed final run.
- Summary, feedback, and annotation bodies reject exact active secret values.
- Run/submit messages, summaries, feedback, annotation bodies, display names, and tags enforce documented UTF-8 byte limits.
- Submit reuse and explicit `--rerun` requirement when no reusable passed run exists.
- Submit-triggered run flow reuses submit `--message` as the run message.
- Submit reuse is limited to the most recent passed run for current HEAD and the experiment bound config version.
- Failed submit keeps final summary, feedback, refs, final commit, and final run id unset.
- Passed submit closes experiment.

## 6. Runner, Reward, Log, And Artifact Tests

Cover:

- Local runner `env_mode` handling.
- `runner.shell` support for local runner and Docker runner shell mode, and rejection for Harbor and SkyDiscover runners.
- Runner environment strips ALab credential variables such as `ALAB_KEY` even under `env_mode = "full"`.
- `env_mode = "full"` renders a stable warning that host env secrets outside `secret_env` are not guaranteed to be redacted.
- Temporary runner workspaces never include `.alab/token` or `.alab/context.json`.
- Fixed internal env injection: `ALAB_PROJECT_ID`, `ALAB_EXP_ID`, `ALAB_RUN_ID`, `ALAB_CONFIG_VERSION`, `ALAB_WORKSPACE`, `ALAB_RUN_DIR`.
- Internal env overrides user env values.
- SkyDiscover Python evaluator-wrapper execution preserves the runner environment boundary, including host ALab credential stripping, internal env override precedence, user env and secret env injection, and hidden-output secret redaction.
- Closed runner stdin behavior.
- Local runner timeout terminates the process group.
- Reward extractors for `exit_code`, `file`, `stdout_regex`, `harbor`, and `skydiscover`.
- File reward read limit reuses artifact per-file limit.
- JSON reward metrics are top-level only.
- Stdout regex reads redacted/truncated stdout.
- Reward parse status behavior for non-zero exit and zero exit.
- Runner start, Docker unavailable, adapter, and dependency-installation errors with saved run/validation records exit `1`, not `5`.
- Source-dependent runner, reward, Dockerfile/context, and artifact paths are schema-validated for safe shape at config time and fail as saved baseline/run records when missing in the selected source snapshot.
- Artifact root parsing and escape rejection.
- Artifact directory expansion.
- Artifact glob capture uses Python glob semantics, escape checks, deduplication by resolved path, and stable sorted output.
- Artifact symlink capture/skip behavior.
- Oversized artifacts skipped without changing run/validation status.
- Artifact capture errors recorded as artifact statuses and `ARTIFACT_CAPTURE_ERROR` warnings without changing run/validation status.
- Failed, errored, reward-parse-error, and timed-out runs/validations still attempt best-effort log and artifact capture when runtime directories remain available.
- Exact-byte artifact export.
- Artifact export overwrite behavior.
- Artifact/log archive and unarchive visibility defaults.
- Artifact/log remove is root/admin-only, requires archived state, and writes audit events.
- Shared artifact blobs and shared log files remain until no row references them.
- Archived artifact/log export requires `--include-archived`; archived artifact/log show by id succeeds when authorized.
- No artifact secret redaction guarantee.
- Configurations with active `secret_env` values and artifact globs render and persist `ARTIFACT_BYTES_NOT_REDACTED` warnings while keeping logs redacted and artifact exports exact.
- Log truncation.
- Byte-based secret redaction before log storage.
- Secret redaction happens before log truncation.
- Log byte-file storage metadata.
- Fixed run previews.
- `observe logs list/show/export`.
- Hidden log authorization requiring root/admin plus `--include-hidden`.
- Hidden log lifecycle preserves hidden permission rules across archive/unarchive/remove attempts.

## 7. Adapter Tests

Docker:

- Docker unavailable marks Docker-backed validation `error` and invalidates project.
- Docker tests skip when Docker is unavailable.
- Docker runner validates repo-relative Dockerfile/context paths.
- Docker runner uses `/app` and `/logs/alab`.
- Docker setup/build output renders `DOCKER_SETUP_OUTPUT_CAPTURED`, stores setup bytes as redacted hidden logs, and does not merge setup bytes into user-visible runner stdout/stderr.
- Docker network modes `default` and `none`.
- `runner.network = "host"` is rejected with `CONFIG_INVALID`.
- Docker runner supports whitelisted `build_args`, `target`, `platform`, `user`, `cpus`, and `memory_mb`.
- Docker-backed runners do not inherit host environment variables.
- Missing `runner.image` images are automatically pulled, with pull failures recorded as saved `RUNNER_ERROR` results when possible.
- Dockerfile build context honors `.dockerignore`, and Dockerfile image cache keys include Dockerfile content, `.dockerignore`, and effective filtered build context.
- Unsupported configured Docker CPU or memory limits fail before config write.
- Dockerfile image cache key includes only build inputs, while run-time fields do not create duplicate cached images.
- Docker runtime capability probes for availability, platform, and resource support are cached by runtime fingerprint and refresh through `config validate --refresh-capabilities`.
- Dockerfile runner creates ALab-owned image cache metadata in `cache_entries` and `cache prune --docker-images|--all` removes it.
- Docker runner rejects raw Docker argument passthrough, privileged mode, and extra host mounts or volumes.
- Unreadable container output records capture errors.

Harbor:

- Single-step Harbor task with shared verifier.
- Single-step Harbor task with separate verifier image.
- Single-step Harbor task with separate verifier `tests/Dockerfile`.
- Default fake-Docker Harbor runner tests must cover shared verifier, separate verifier image, separate `tests/Dockerfile` build/cache metadata, hidden verifier logs, secret redaction, Docker run argument shape, hostless environment behavior, internal env override precedence, Harbor task env injection, and external secret env injection.
- Verifier workspace mount is temporary and writable.
- Hidden verifier logs are admin-only.
- Harbor CPU/memory/network mapping.
- Harbor task text precedence.
- Harbor imports declared safe task-relative source as editable source, falls back to empty source, and never imports `tests/`, `environment/`, `solution/`, verifier assets, or task-private files.
- Harbor literal task env values are injected as `secret_env` values and redacted.
- Placeholder rejection.
- Unsupported Windows tasks rejected.
- Unsupported multi-step tasks rejected.
- Unsupported Docker Compose, GPU, MCP, healthcheck, external service, storage, and scheduling fields rejected.
- Unsupported raw Docker passthrough and task-declared extra host mounts rejected.
- `solution/` never becomes editable source.

SkyDiscover:

- Catalog add/update default to the official URL and upstream `main`, support `--origin-url`, `--ref`, and `--commit`, and always store a pinned exact commit.
- Catalog show does not fetch network.
- Catalog update dirty state failure.
- Catalog remove is root-only and blocked while active configs or open experiments bound to catalog-backed configs reference catalog tasks or evaluator bundles.
- Closed and archived experiment history remains observable after catalog removal.
- SkyDiscover catalog add/update pins an exact upstream commit and never follows `main` automatically.
- Missing catalog path does not auto-update.
- Missing active SkyDiscover catalog fails with a next action to `catalog skydiscover add`; missing catalog paths never auto-fetch or auto-update.
- Source precedence: explicit editable sources for adapter project init are limited to `--source-path`, `--source-git`, or `--source-empty`, and `--source-ref` is rejected.
- Initial program file import when no explicit source is supplied.
- Initial program directory import when no explicit source is supplied.
- Missing initial program fails and asks for explicit source.
- Only initial file/directory is imported, not the whole benchmark.
- Docker evaluator parses top-level metrics.
- Docker evaluator fake-Docker coverage proves the hidden evaluator bundle mount, workspace/program/run-dir env values, hostless environment, internal env override precedence, secret env injection, and hidden stderr redaction.
- Python evaluator uses wrapper subprocess and never imports evaluator code into main process.
- SkyDiscover Python evaluator is a required full V1 adapter capability, not an experimental or V2-only feature.
- Python evaluator renders explicit non-OS-sandbox warnings in safe root/admin summaries.
- Python evaluator creates/reuses `uv` dependency environment by dependency file hash.
- Python evaluator environment cache key includes dependency file hashes, platform, and Python version, and dependency installation may use the default network.
- Cache prune root-only behavior for Docker image caches, SkyDiscover evaluator environments, and `--all`.
- Backup prune root-only behavior for `--keep <n>` and `--older-than <days>`.
- Default SkyDiscover metric fallback averages finite numeric top-level metrics.
- Missing explicitly configured primary metric fails with `REWARD_PARSE_ERROR`.
- SkyDiscover search/proposal/mutation loops are not called.

## 8. Observe And Collaboration Tests

Cover:

- Visibility `none`, `same_project`, and `explicit` narrowing.
- Token contexts always see their own experiment records; visibility scope controls only other experiments.
- Effective token visibility is current project policy intersected with the experiment's stored policy.
- Later project policy broadening can broaden existing token visibility within the stored experiment policy bound.
- Public no-key `exp create --from-exp` visibility is current project public policy intersected with the source experiment's stored visibility upper bound.
- Observe filters, pagination, sorting, and best ranking.
- Invalid-project `best` uses the active valid reward policy identity by default; when none exists it requires explicit `--config-version`.
- Best ranking excludes runs with incomparable reward policy identity and renders `BEST_INCOMPARABLE_RUNS_EXCLUDED`.
- Best ranking can compare across config versions only when reward policy identity matches.
- Search corpus includes allowed text and excludes logs/artifact bytes/history revisions.
- Archived experiments hidden by default from list/search/best.
- Tags add/remove/list by creator token and admin.
- Tags never grant visibility.
- Regenerated worktree tokens for the same experiment can see and edit experiment-private annotations because private annotation ownership is experiment-bound.
- Regenerated worktree tokens inherit own-experiment archive/unarchive permissions for runs, artifacts, and visible logs.
- Annotation target parsing.
- Annotation `target_json` stores resolved target details.
- Project-visible annotations do not expand target record visibility; callers must be able to see both the annotation scope and the target record.
- Annotation common commitish aliases and SHA resolution to concrete commit at creation.
- Annotation line validation.
- Current experiment shorthand path/line annotations require a clean worktree and anchor to HEAD.
- Root/admin project-context annotation body checks use the target experiment's bound `secret_env` values.
- Project-context annotation targets that do not resolve to exactly one experiment are rejected before body storage.
- Private annotation visibility.
- Private annotations remain private when project visibility later broadens.
- Annotation archive behavior.
- Annotation unarchive behavior.
- Annotation remove by creator/admin/root, archived-state requirement, revision deletion, and audit event creation.
- Annotation revision history.
- Annotation body text/file-only input and stdin rejection.
- Inspection checkout creates detached HEAD and inspection token.
- Inspection observe/export uses pinned records when local files become dirty.
- Inspection tokens rejected for mutation commands.
- Hidden validation assets absent from experiment and inspection worktrees after project init, run, submit, and checkout.
- Experiment and inspection tokens cannot view hidden verifier scripts, hidden test data, raw hidden logs, Harbor verifier bundles, or SkyDiscover evaluator bundles through status, observe, artifacts, or config summaries.
- Project remove with `--cascade` deletes an archived project as a whole-tree operation without requiring child records to be individually archived.
- Experiment remove with `--cascade` deletes an archived experiment's child runs, artifacts, logs, annotations, tags, inspection contexts, worktree, and submission records without requiring those child records to be individually archived.
- Source remove remains strict: config-version references always block removal, and experiment references require dependent experiments to be archived before source cascade can proceed.

## 9. Acceptance Gates

Core usable milestone is ready when:

- Local auth, root regeneration, admin keys, credentials, context, local/Git/empty source import, project validation, experiment create, run, submit, observe basics, tags, annotations, logs, and artifacts pass tests on macOS and Linux.
- Public/private collaboration boundaries behave as documented.
- Text output goldens are stable.
- No raw root/admin keys or experiment tokens are stored or rendered outside creation/token-file rules; plaintext `secret_env` values remain local-only and are never rendered or exported.

Full V1 is ready when:

- Docker runner works where Docker is available.
- Docker-dependent real-environment tests are opt-in with `ALAB_RUN_REAL_DOCKER=1`, skip when Docker, the daemon, or required images are unavailable, and cover Docker image runner command and shell execution, real container environment isolation/internal `ALAB_*` overrides, Dockerfile runner build context and cache reuse, Harbor shared verifier, Harbor separate verifier image, Harbor separate `tests/Dockerfile`, Harbor real-container environment isolation/internal `ALAB_*` overrides/task-env/external secret injection, SkyDiscover Docker evaluator execution, SkyDiscover Docker real-container environment isolation/internal `ALAB_*` overrides/secret injection, and real Docker image-cache reuse for Dockerfile-backed adapter images.
- SkyDiscover Python real-environment dependency-installation tests are opt-in with `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1`, skip when `uv` is unavailable, and use a locally generated wheel so the dependency path can be verified without network access.
- Networked SkyDiscover Python dependency-installation tests are opt-in with `ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1`, skip by default, and install direct and transitive pure-Python dependency cases from the configured package index through the evaluator environment.
- Native/binary SkyDiscover Python dependency-installation tests are opt-in with `ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1`, skip by default, and install a native package through the evaluator environment from the configured package index. The default package is `orjson>=3.10,<4`, with `ALAB_NATIVE_SKYDISCOVER_PYTHON_REQUIREMENT` and `ALAB_NATIVE_SKYDISCOVER_PYTHON_MODULE` overrides for platform-specific package-index validation.
- Live SkyDiscover catalog tests are opt-in with `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1`, skip when `git` or the official catalog remote is unavailable, and verify live clone/pin behavior, no-network `catalog show`, and resolving a real evaluator ref through project init with baseline validation skipped.
- Harbor single-step shared/separate verifier tasks work and unsupported Harbor features fail clearly.
- SkyDiscover catalog, Docker evaluator, and Python evaluator work.
- Hidden validation asset rules hold for all adapters.
- The complete test suite covers local workflow, invalid project behavior, public/private permissions, source imports, run/submit behavior, observe, annotations, runner adapters, and collaboration boundaries.
