# ALab V1 CLI Spec

This spec defines ALab V1 command shape, global options, output, debug behavior, command contracts, and error mapping. It is normative for CLI implementation and tests.

## 1. Invocation Model

Canonical invocation:

```text
alab [--home <path>] [--output text|rich] [--key <secret>] [--key-stdin] [<command> [args]]
```

Rules:

- Global options may appear before or after the canonical command or top-level alias.
- The CLI pre-scans argv for global options before context detection, migration, config loading, credential lookup, or command-specific parsing.
- Pre-scan stops at the first standalone `--`. Arguments after `--` are passed to command-specific parsing and are never interpreted as global `--home`, `--output`, `--key`, or `--key-stdin` options.
- Duplicate global options fail with exit code `2` except where an option explicitly accepts repeated values.
- Canonical nested commands are the documented source of truth. Aliases must map to the same handler and result schema.
- Running `alab` with no command, `alab help`, `alab --help`, or a nested command help request invokes the context-aware capability help surface.
- `--home` applies before context detection, migration, config loading, or credential lookup.
- `--output` selects rendering for one command only.
- `--key` supplies a root or project admin key.
- `--key-stdin` reads all stdin, strips at most one trailing newline, and then requires a non-empty single-line value with no NUL bytes. Empty input, embedded newlines, and NUL bytes fail with `CONFIG_INVALID`. It conflicts with `--key`.
- `ALAB_KEY` is used only when neither `--key` nor `--key-stdin` is present and the command requires root/admin authorization.
- Commands that are public or optionally authorized must ignore `ALAB_KEY` for privilege elevation. They may render authorized details only when `--key` or `--key-stdin` is supplied explicitly.

Home resolution priority:

1. `--home <path>`
2. `ALAB_HOME`
3. `~/.ALab`

Context-aware capability surface:

- ALab maintains one canonical command registry, but the visible and executable command surface is filtered by the current context and the verified credential source.
- The capability resolver is used by `alab`, `alab help`, `alab --help`, nested command help requests, and command execution preflight. Help output and command preflight must use the same allow/lock decision for a given argv, context, and explicit credential.
- The resolver runs after global option pre-scan, home resolution, migration, global config loading, context detection, and explicit credential or context-token lookup. It runs before command-specific parsing that reads user body/value files, before Git operations, before SQLite writes other than required read-only lookup and stale migration setup, before runner execution, and before lifecycle audit rows.
- Default capability uses the current context token when the current context is an experiment or inspection checkout. Project context without an explicit key exposes only public project capabilities. Outside any context, only global public commands and commands with explicit target options that are context-compatible are candidates.
- Explicit `--key` or `--key-stdin` unlocks the matching credential surface: a project admin key unlocks same-project admin capabilities; the root key unlocks root capabilities. Existing context-conflict rules still apply, so a root key does not allow a command to operate on a different explicit project while the cwd is inside another active ALab context.
- `ALAB_KEY` does not affect `alab`, `alab help`, `alab --help`, nested command help, or any dynamic capability display. During execution, `ALAB_KEY` may still satisfy root/admin authentication only when the command is already available in the current context surface and requires root/admin authorization. It must not broaden an experiment, inspection, or public project surface into an admin/root surface.
- If a user directly invokes a command that is not in the current executable surface, ALab fails with `COMMAND_UNAVAILABLE` exit `4`. This is a pre-handler availability failure, not a replacement for handler-level `AUTH_REQUIRED`, `AUTH_DENIED`, or `SCOPE_VIOLATION`.
- Capability preflight is not an authentication shortcut. If a command is valid in the current context surface but requires root/admin credentials, missing or invalid credentials still use the existing `AUTH_REQUIRED` or `AUTH_DENIED` contract. `COMMAND_UNAVAILABLE` is for commands the current context/token/public surface does not expose at all, such as project config mutation from an experiment token surface without an explicit admin/root key.
- Hidden commands are hidden by default to reduce agent distraction. `alab help --all` may show locked commands, but locked entries must use safe reasons and unlock hints only; they must not disclose secret names or values, hidden logs, hidden assets, absolute hidden paths, invisible object existence, or private adapter staging paths.

## 2. Output Model

Command handlers return structured result objects. Renderers convert those objects to CLI output.

V1 renderers:

- `text`: default, persisted, stable, agent-friendly output.
- `rich`: optional human-friendly output, selected only by `--output rich` for one command.

V1 exposes no `json`, `xml`, or hidden experimental structured output mode. The renderer boundary may support additional formats in a future version, but V1 compatibility is defined only by stable structured result objects rendered as `text` and single-command `rich`.

Global config path:

```text
~/.ALab/config.toml
```

Valid persisted global config:

```toml
schema_version = 1

[output]
format = "text"
preview_bytes = 4096

[storage]
busy_timeout_ms = 5000

[locks]
acquire_timeout_ms = 30000
heartbeat_interval_ms = 5000
stale_after_ms = 120000
```

Rules:

- `format = "text"` is the only valid persisted output value.
- `format = "rich"` fails with `CONFIG_INVALID`.
- Time values are integer milliseconds.
- Invalid global config blocks normal commands after home resolution and migration. `auth init` and `config show|set|reset|validate` remain available for repair.
- Rich output uses the same result data as text output. It must not expose additional secrets, hidden paths, hidden logs, or hidden asset contents.
- Typer Rich help and pretty exceptions are disabled by default.
- Text output is a strict key-value object format. Each rendered object starts with `object: <type>`.
- Each scalar field renders as `field: value`.
- Multiple objects render as repeated object blocks separated by exactly one blank line.
- Nullable fields render absent values as `none`; the literal string `none` in user-provided text is never coerced to null.
- Booleans render as `true` or `false`.
- Lists always render as repeated labeled lines, one value per line, using the command's documented singular label. Empty lists render no repeated lines unless the command result schema includes an explicit count or summary scalar. Text output never uses comma-separated list rendering.
- Multiline text fields render as `field:` followed by each content line prefixed with two spaces. Nullable multiline fields with absent values render `field: none`; non-null empty multiline strings render as `field:` followed by `  [empty]`.
- User-provided text fields such as task, goal, run messages, submission summaries, feedback, and annotation bodies always render as multiline text fields. Empty user-provided text renders as `field:` followed by `  [empty]`, so it is distinct from nullable `none` and from the literal text `none`.
- Warnings render after all primary result objects as `object: warning` blocks, one block per warning, in production order.
- Error output also uses object blocks. System/internal failures render `object: error`; saved result failures render the command's normal result object plus `error code`, `exit code`, `reason`, and `next` fields.
- Help output is also rendered from structured capability result objects. Default help renders only available commands. `--all` may render locked commands after available commands, with locked reason and unlock hint fields that are safe for the current caller.

## 3. Debug Mode

`ALAB_DEBUG=1` affects internal/system failures only.

Allowed:

- Print the normal ALab error template.
- Print the exception type.
- Print a full stack trace for the internal failure.

Forbidden:

- Locals or object dumps.
- Environment maps.
- Raw root keys, admin keys, or experiment tokens.
- `secret_env` names paired with values, raw secret values, or verifier hashes.
- Hidden asset contents.
- Raw hidden verifier/evaluator logs.
- Hidden staging paths when those paths disclose private assets.

Result failures, such as a failed run or failed baseline with a saved record, do not print stack traces even in debug mode.

## 4. Error And Warning Output

System/internal failure template:

```text
object: error
message: Command failed.
error code: PROJECT_INVALID
exit code: 4
project id: proj-example-a1b2
reason: project baseline validation is invalid
next: alab project validate --project proj-example-a1b2 --key <root-or-admin-key>
```

Result-failure rules:

- A command that successfully records a failed result exits with code `1`.
- Examples are failed runs, failed baseline validation, timeout with a saved record, and submit not accepted.
- Result failures render the relevant structured fields, including ids, status, reward parse status when relevant, log/artifact capture summary, stable error code, numeric exit code, reason, and next action.
- Result failures do not use the internal/system failure template unless ALab itself could not execute the command flow.

Warning output:

```text
object: warning
warning code: TOKEN_FILE_PERMISSIONS
warning reason: token file permissions are broader than 0600
```

Warnings are stable fields, not free-form prose. A command may render multiple warnings.

V1 warning codes include:

- `TOKEN_FILE_PERMISSIONS`
- `TRACKED_SENSITIVE_SOURCE_FILE`
- `SOURCE_EMPTY_AFTER_FILTER`
- `SOURCE_DEDUPED_NAME_IGNORED`
- `PUBLIC_GIT_CREDENTIAL_HELPER_USED`
- `ENV_MODE_FULL_UNREDACTED_HOST_ENV`
- `ARTIFACT_BYTES_NOT_REDACTED`
- `BEST_INCOMPARABLE_RUNS_EXCLUDED`

## 5. Error Codes And Numeric Exit Codes

Stable error codes:

- `AUTH_REQUIRED`
- `AUTH_DENIED`
- `HOME_EXISTS`
- `CONTEXT_NOT_FOUND`
- `CONTEXT_CONFLICT`
- `PROJECT_NOT_FOUND`
- `PROJECT_INVALID`
- `PROJECT_ARCHIVED`
- `EXPERIMENT_NOT_FOUND`
- `EXPERIMENT_CLOSED`
- `EXPERIMENT_ARCHIVED`
- `RUN_NOT_FOUND`
- `VALIDATION_NOT_FOUND`
- `SOURCE_NOT_FOUND`
- `SOURCE_INVALID`
- `SOURCE_LIMIT_EXCEEDED`
- `ARTIFACT_NOT_FOUND`
- `LOG_NOT_FOUND`
- `ANNOTATION_NOT_FOUND`
- `CREDENTIAL_NOT_FOUND`
- `AUDIT_NOT_FOUND`
- `CATALOG_NOT_FOUND`
- `CACHE_NOT_FOUND`
- `COMMAND_UNAVAILABLE`
- `NAME_CONFLICT`
- `SCOPE_VIOLATION`
- `EXPERIMENT_BUSY`
- `RESOURCE_BUSY`
- `GIT_STATE_INVALID`
- `GIT_ERROR`
- `RUNNER_FAILED`
- `RUNNER_TIMEOUT`
- `RUNNER_ERROR`
- `REWARD_PARSE_ERROR`
- `CONFIG_INVALID`
- `BASELINE_VALIDATION_FAILED`
- `OUTPUT_EXISTS`
- `STORAGE_ERROR`

Numeric exit codes:

| Exit code | Category | Examples |
| --- | --- | --- |
| 0 | Success | command succeeded; run/validation/submit accepted |
| 1 | Result failed | run failed, final submit not accepted, baseline failed, timeout with record saved |
| 2 | Usage/config | invalid CLI arguments, schema invalid, bad TOML literal, source import limit exceeded, duplicate name |
| 3 | Auth | missing/invalid root/admin key, revoked key |
| 4 | Context/scope | context conflict, scope violation, mutable violation, closed experiment |
| 5 | System/internal | storage failure, Git subprocess failure, runner could not start, migration failure |

Stable error-code exit mapping:

| Error code | Exit |
| --- | --- |
| `AUTH_REQUIRED` | 3 |
| `AUTH_DENIED` | 3 |
| `HOME_EXISTS` | 2 |
| `CONTEXT_NOT_FOUND` | 2 |
| `CONTEXT_CONFLICT` | 4 |
| `PROJECT_NOT_FOUND` | 2 |
| `PROJECT_INVALID` | 4 |
| `PROJECT_ARCHIVED` | 4 |
| `EXPERIMENT_NOT_FOUND` | 2 |
| `EXPERIMENT_CLOSED` | 4 |
| `EXPERIMENT_ARCHIVED` | 4 |
| `RUN_NOT_FOUND` | 2 |
| `VALIDATION_NOT_FOUND` | 2 |
| `SOURCE_NOT_FOUND` | 2 |
| `SOURCE_INVALID` | 2 |
| `SOURCE_LIMIT_EXCEEDED` | 2 |
| `ARTIFACT_NOT_FOUND` | 2 |
| `LOG_NOT_FOUND` | 2 |
| `ANNOTATION_NOT_FOUND` | 2 |
| `CREDENTIAL_NOT_FOUND` | 2 |
| `AUDIT_NOT_FOUND` | 2 |
| `CATALOG_NOT_FOUND` | 2 |
| `CACHE_NOT_FOUND` | 2 |
| `COMMAND_UNAVAILABLE` | 4 |
| `NAME_CONFLICT` | 2 |
| `SCOPE_VIOLATION` | 4 |
| `EXPERIMENT_BUSY` | 4 |
| `RESOURCE_BUSY` | 4 |
| `GIT_STATE_INVALID` | 4 |
| `GIT_ERROR` | 5 |
| `RUNNER_FAILED` | 1 |
| `RUNNER_TIMEOUT` | 1 |
| `RUNNER_ERROR` | 1 when a run or validation record is saved; otherwise `STORAGE_ERROR` or `GIT_ERROR` exit `5` applies |
| `REWARD_PARSE_ERROR` | 1 |
| `CONFIG_INVALID` | 2 |
| `BASELINE_VALIDATION_FAILED` | 1 |
| `OUTPUT_EXISTS` | 2 |
| `STORAGE_ERROR` | 5 |

Rules:

- Each stable error code maps to the exit code above. Command-specific matrices may add likely codes and next actions, but they must not remap exits.
- All future `*_NOT_FOUND` codes default to exit `2`.
- `COMMAND_UNAVAILABLE` is reserved for capability preflight. It means the command is not available in the current context and credential surface. It must be returned before command-specific side effects and must not reveal whether hidden objects exist.
- Result failures with a saved run or validation record exit `1`, including runner start errors, Docker unavailable validation records, dependency installation failures, and adapter errors that are captured into a final `error` status.
- If ALab cannot create or finalize the intended result record, the command fails as a system/internal error using `STORAGE_ERROR`, `GIT_ERROR`, or another applicable exit `5` code.

Input normalization and lookup rules:

- ALab object id parameters require complete ids. This includes home, project, source, experiment, run, validation, artifact, log, annotation, credential, token, audit, catalog, and cache ids.
- Git commit selectors may be full SHAs or unambiguous abbreviated SHAs when the command explicitly accepts a commit selector.
- Time filter options such as `--created-after`, `--created-before`, `--started-after`, and `--ended-before` accept only RFC 3339 timestamps with `Z` or an explicit numeric offset. ALab normalizes accepted times to UTC `Z` for queries and output.
- Unknown object ids use the most specific `*_NOT_FOUND` code when one exists; otherwise they use `CONFIG_INVALID` for invalid selectors or filters.
- Token-scoped and public callers selecting an object that exists but is not visible receive `SCOPE_VIOLATION` with a non-disclosing reason such as `not visible or not found`. Public and token-scoped output must not reveal whether the object exists outside the caller's visibility. Root/admin callers receive precise `*_NOT_FOUND` or scope errors.

Command error matrix:

- Every command may fail with `STORAGE_ERROR` exit `5` for storage, migration, backup, or unexpected SQLite failures.
- Every command that runs Git may fail with `GIT_ERROR` exit `5`; commands that validate user worktree state before Git mutation use `GIT_STATE_INVALID` exit `4`.
- Every command requiring root/admin credentials may fail with `AUTH_REQUIRED` or `AUTH_DENIED` exit `3`.
- Every token-scoped command may fail with `AUTH_REQUIRED`, `AUTH_DENIED`, `CONTEXT_NOT_FOUND`, `CONTEXT_CONFLICT`, or `SCOPE_VIOLATION` as applicable.
- Every command except help may fail with `COMMAND_UNAVAILABLE` exit `4` when the context-aware capability resolver rejects the command before handler execution.
- Commands that write lifecycle audit events render `audit id` on success unless a command-specific secret rule forbids it.

| Command family | Stable failure codes |
| --- | --- |
| `help`, no-command `alab`, `--help`, nested command help | `COMMAND_UNAVAILABLE` does not apply; `CONFIG_INVALID` exit `2` for invalid help selectors; `STORAGE_ERROR` exit `5` |
| `auth init` | `HOME_EXISTS` exit `2`; `STORAGE_ERROR` exit `5` |
| `auth root regenerate` | `AUTH_REQUIRED`, `AUTH_DENIED` exit `3`; `STORAGE_ERROR` exit `5` |
| `config show|set|reset|validate` | `CONFIG_INVALID` exit `2`; `STORAGE_ERROR` exit `5` |
| `key create|list|revoke` | `AUTH_REQUIRED`, `AUTH_DENIED` exit `3`; `PROJECT_NOT_FOUND`, `CREDENTIAL_NOT_FOUND`, or `CONFIG_INVALID` exit `2` |
| `context show|repair` | `CONTEXT_NOT_FOUND` exit `2`; `CONTEXT_CONFLICT`, `SCOPE_VIOLATION` exit `4`; `AUTH_REQUIRED`, `AUTH_DENIED` exit `3`; invalid path `CONFIG_INVALID` exit `2` |
| `project list|show|status` | `AUTH_REQUIRED`, `AUTH_DENIED` exit `3`; `PROJECT_NOT_FOUND` exit `2`; `CONTEXT_CONFLICT` exit `4` |
| `project archive|unarchive` | `PROJECT_NOT_FOUND` exit `2`; `RESOURCE_BUSY` exit `4`; auth failures exit `3`; already matching archive state exits `0` |
| `project remove` | missing confirmation `CONFIG_INVALID` exit `2`; `PROJECT_NOT_FOUND` exit `2`; not archived or blockers `RESOURCE_BUSY` exit `4`; auth failures exit `3` |
| `project init` | invalid config `CONFIG_INVALID` exit `2`; invalid or conflicting source `SOURCE_INVALID` exit `2`; failed baseline `BASELINE_VALIDATION_FAILED` exit `1`; auth failures exit `3` |
| `project config/env/secret` | invalid field/value/retain marker `CONFIG_INVALID` exit `2`; missing active valid version `PROJECT_INVALID` exit `4`; baseline failure `BASELINE_VALIDATION_FAILED` exit `1`; auth failures exit `3`; `OUTPUT_EXISTS` exit `2` for export |
| `project validate` | failed/error/timeout validation `BASELINE_VALIDATION_FAILED` exit `1`; `PROJECT_NOT_FOUND` exit `2`; auth failures exit `3` |
| `project validation archive|unarchive|remove` | `PROJECT_NOT_FOUND`, `VALIDATION_NOT_FOUND`, or `CONFIG_INVALID` exit `2`; active/not archived/blockers `RESOURCE_BUSY` exit `4`; auth failures exit `3`; already matching archive state exits `0` |
| `project locks clear-stale` | `PROJECT_NOT_FOUND` exit `2`; auth failures exit `3` |
| `backup prune` | invalid retention selector `CONFIG_INVALID` exit `2`; auth failures exit `3` |
| `audit list|show` | invalid filters `CONFIG_INVALID` exit `2`; `AUDIT_NOT_FOUND` exit `2`; auth failures exit `3` |
| `source import` | `SOURCE_INVALID`, `SOURCE_LIMIT_EXCEEDED`, `NAME_CONFLICT` exit `2`; `PROJECT_NOT_FOUND` exit `2`; auth failures exit `3` |
| `source list|show` | `SOURCE_NOT_FOUND` or `PROJECT_NOT_FOUND` exit `2`; auth failures exit `3` |
| `source archive|unarchive|remove` | `SOURCE_NOT_FOUND`, `CONFIG_INVALID` exit `2`; active default, not archived, or blockers `RESOURCE_BUSY` exit `4`; auth failures exit `3`; already matching archive state exits `0` |
| `catalog skydiscover add|update|show|remove` | invalid selector/dirty catalog/existing catalog `CONFIG_INVALID` exit `2`; `CATALOG_NOT_FOUND` exit `2`; active references `RESOURCE_BUSY` exit `4`; auth failures exit `3` |
| `cache prune` | invalid selector combination `CONFIG_INVALID` exit `2`; auth failures exit `3` |
| `exp create` | invalid source/name/path `CONFIG_INVALID`, `SOURCE_INVALID`, or `NAME_CONFLICT` exit `2`; invalid project state `PROJECT_INVALID` or `PROJECT_ARCHIVED` exit `4`; auth failures exit `3` |
| `exp archive|unarchive|remove` | `EXPERIMENT_NOT_FOUND` or `CONFIG_INVALID` exit `2`; active lock/not archived/blockers `RESOURCE_BUSY` exit `4`; auth failures exit `3`; already matching archive state exits `0` |
| `exp checkout|checkout remove` | invalid path/commit/selector `CONFIG_INVALID` exit `2`; visibility/scope failures `SCOPE_VIOLATION` exit `4`; auth failures exit `3` |
| `exp worktree remove|restore` | invalid path/confirmation `CONFIG_INVALID` exit `2`; cleanup failure or context nesting `RESOURCE_BUSY` or `CONTEXT_CONFLICT` exit `4`; auth failures exit `3` |
| `exp token list|revoke|regenerate` | invalid selector `CONFIG_INVALID` exit `2`; `EXPERIMENT_NOT_FOUND` or `CREDENTIAL_NOT_FOUND` exit `2`; auth failures exit `3` |
| `exp tag add|remove|list` | invalid tag `CONFIG_INVALID` exit `2`; scope failures `SCOPE_VIOLATION` exit `4`; auth failures exit `3` |
| `run` | failed/error/timeout run `RUNNER_FAILED`, `RUNNER_ERROR`, `RUNNER_TIMEOUT`, or `REWARD_PARSE_ERROR` exit `1`; mutable violations `SCOPE_VIOLATION` exit `4`; invalid Git state `GIT_STATE_INVALID` exit `4`; busy experiment `EXPERIMENT_BUSY` exit `4` |
| `submit` | final run not accepted `RUNNER_FAILED`, `RUNNER_ERROR`, `RUNNER_TIMEOUT`, `REWARD_PARSE_ERROR`, or missing reusable run exit `1`; invalid refs/inputs `CONFIG_INVALID` exit `2`; closed/scope failures exit `4` |
| `observe experiments|runs|artifacts|logs|annotations` | invalid filters/sort/selector `CONFIG_INVALID` exit `2`; object not found with the matching `EXPERIMENT_NOT_FOUND`, `RUN_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `LOG_NOT_FOUND`, or `ANNOTATION_NOT_FOUND` exit `2` for root/admin; token/public not-visible-or-not-found selectors `SCOPE_VIOLATION` exit `4`; export target `OUTPUT_EXISTS` exit `2`; auth failures exit `3`; archive/unarchive already matching state exits `0` |
| `annotate add|edit|archive|unarchive|remove` | invalid target/body/confirmation `CONFIG_INVALID` exit `2`; `ANNOTATION_NOT_FOUND` exit `2` for root/admin; token/public not-visible-or-not-found selectors and other visibility/scope failures `SCOPE_VIOLATION` exit `4`; auth failures exit `3`; archive/unarchive already matching state exits `0` |

## 6. Context And Credential Terms

Context values used below:

- Global: no project or experiment context required.
- Project: project control directory or explicit `--project`.
- Experiment: registered experiment worktree with `.alab/context.json` and `.alab/token`.
- Inspection: registered read-only ALab context created by `exp checkout`.
- Any: command may run from any path after home resolution.

Credential values:

- None: no key or token.
- Root: root key.
- Admin: project admin key.
- Root/admin: either root key or the matching project admin key.
- Token: valid worktree or inspection token, depending on command.
- Public: no key when project policy allows the operation.

Capability surface terms:

- Available: the command is shown in default help and may enter its command handler after normal command-specific parsing.
- Locked: the command exists in the canonical registry but is not currently available because the active context, credential source, project policy, or token mode does not expose it.
- Hidden: locked commands are omitted from default help. They appear only in `alab help --all`, with safe locked reason and unlock hint fields.
- Credential source: one of `none`, `public`, `context-token`, `explicit-admin`, `explicit-root`, or `ambient-env`. `ambient-env` is never used for help capability display and never broadens token or public context surfaces.
- Capability source: the rule that made a command available, such as `global`, `public-project`, `worktree-token`, `inspection-token`, `project-admin`, or `root`.

Default context surfaces:

- Global with no explicit key: show `help`, `auth init`, config diagnostics/repair, and context diagnostics commands that do not require a project record. Commands that require a project may be available only when they include an explicit target and do not conflict with the current path.
- Global with explicit project admin key: show the matching project's admin surface and commands that can run with that credential by passing its project id explicitly.
- Global with explicit root key: additionally show root-level project creation, project listing, key management, catalog, cache, backup, and audit commands.
- Project context with no explicit key: show public safe `status`; when project policy allows public experiment creation, show public `exp create` with source bootstrap options. Hide project management, source management, config, validation, audit, cache, catalog, backup, key, and lifecycle maintenance commands.
- Project context with explicit project admin key: show same-project project/source/config/validate/observe/experiment management commands except root-only commands.
- Project context with explicit root key: show project admin capabilities plus root-only commands in scope.
- Experiment context with worktree token: show `status`, `run`, `submit`, visible observe commands, own-experiment tag commands, authorized annotations, and own-experiment run/artifact/visible-log archive or unarchive commands. Hide project/source/config/project init, experiment remove, worktree maintenance, key management, audit, cache, catalog, and backup commands.
- Experiment context with explicit project admin or root key: unlock the matching same-project admin or root surface while preserving existing context-conflict rules for different explicit projects.
- Inspection context with inspection token: show `status`, visible observe commands, artifact/log export, and removal of its own inspection checkout. Hide run, submit, tag mutation, annotation mutation, project/source/config management, experiment mutation, worktree maintenance, key management, audit, cache, catalog, and backup commands.
- Inspection context with explicit project admin or root key: unlock the matching same-project admin or root surface while preserving inspection-token read-only behavior when no explicit key is provided.

## 7. Command Groups And Aliases

Canonical groups:

- `help`
- `auth`
- `config`
- `key`
- `context`
- `project`
- `source`
- `catalog`
- `cache`
- `backup`
- `audit`
- `exp`
- `observe`
- `annotate`

Top-level aliases:

- `alab` with no command and `alab --help` map to `alab help`.
- `alab status` maps to project/experiment/inspection status.
- `alab run` is canonical for experiment run.
- `alab submit` is canonical for experiment submit.
- `alab exp list|search|show|best` map to `observe experiments ...`.
- `alab runs list|show|archive|unarchive|remove` map to `observe runs ...`.
- `alab artifacts list|show|export|archive|unarchive|remove` map to `observe artifacts ...`.
- `alab logs list|show|export|archive|unarchive|remove` map to `observe logs ...`.
- `alab annotations list|show` map to `observe annotations ...`.

Alias policy:

- V1 supports only the aliases listed in this section.
- `alab run` and `alab submit` are canonical top-level commands; V1 does not add `alab exp run` or `alab exp submit` aliases.
- Help aliases use the capability resolver before rendering. They do not use ambient `ALAB_KEY` to expand the visible surface.
- Any future alias must map to an existing handler and structured result schema and must add golden tests before it is accepted.

## 8. Command Contracts

Every command must have golden tests for text success output, text error output, alias behavior when an alias exists, and global option placement before and after the command.

The command contracts below are the normative text-output schemas:

- `Object type` identifies the exact `object: <type>` value for the primary result block.
- `Success fields` are listed in exact render order. A renderer must not reorder fields, add storage-only fields, or omit non-null listed fields unless a command-specific rule marks the field conditional.
- `Success fields per <type>` means the command renders zero or more `object: <type>` blocks, one per returned row, with the listed fields in order.
- Repeated fields render one line per value using the singular label named in the command contract. Repeated object rows render as separate object blocks.
- Dry-run remove commands use the same object type as the actual remove command and include blocker and count fields after the base success fields in stable order defined by the command's golden tests.
- Result-failure records, such as failed runs or validations with saved rows, use the command's normal primary object type and field order, then append `error code`, `exit code`, `reason`, and `next` fields.
- System/internal failures use only `object: error` as defined above. Warnings always render after primary result objects as `object: warning`.

Primary object types:

| Command pattern | Object type |
| --- | --- |
| `help`, no-command `alab`, `--help`, and nested command help | `help` |
| repeated command rows from help output | `help_command` |
| `auth init`, `auth root regenerate` | `auth` |
| `config show|set|reset|validate` | `config` |
| repeated capability rows from `config validate` | `capability` |
| `key create|list|revoke`, `exp token list|revoke|regenerate` | `credential` |
| `context show|repair` | `context` |
| `project list|show|archive|unarchive|remove`, `status` in project/public mode | `project` |
| `project config show|export|import|set` | `project_config` |
| `project env set|unset|list` | `project_env` |
| `project secret set|unset|list|gc` | `project_secret` |
| `project validate`, `project validation archive|unarchive|remove` | `validation` |
| `project locks clear-stale` | `lock_clear` |
| `backup prune` | `backup_prune` |
| `audit list|show` | `audit` |
| `source import|list|show|archive|unarchive|remove` | `source` |
| `catalog skydiscover add|update|show|remove` | `catalog` |
| `cache prune` | `cache_prune` |
| `exp create|list|search|show|best|archive|unarchive|remove`, `status` in experiment mode | `experiment` |
| `exp checkout`, `exp checkout remove`, `status` in inspection mode | `inspection_checkout` |
| `exp worktree remove|restore` | `worktree` |
| `exp tag add|remove|list` | `tag` |
| `run`, `observe runs list|show|archive|unarchive|remove` | `run` |
| `submit` | `submission` |
| `observe artifacts list|show|export|archive|unarchive|remove` | `artifact` |
| `observe logs list|show|export|archive|unarchive|remove` | `log` |
| `annotate add|edit|archive|unarchive|remove`, `observe annotations list|show` | `annotation` |

Lifecycle command rules:

- Archive and unarchive commands are idempotent. Repeating an operation against an object already in the requested state exits `0`, renders the unchanged state, and does not create a duplicate audit event.
- `remove --dry-run` exits `0` even when the target is not archived, renders a stable `target_not_archived` blocker, and never writes audit rows or deletes data.
- Actual `remove` still fails when the target is not archived.

### Help

`alab help [--all] [--explain]`, no-command `alab`, `alab --help`, and nested command help requests

- Context: Any.
- Credential: None, context token, or explicit root/admin key.
- Options: `--all`, `--explain`.
- Ambient env rule: ignores `ALAB_KEY` for capability display.
- Availability rule: default help includes only commands available for the current context and credential source.
- Full listing rule: `--all` includes locked commands after available commands, with safe locked reasons and unlock hints.
- Explanation safety rule: `--explain` renders context and credential-source explanation fields, but must not render raw tokens, raw keys, secret names or values, verifier hashes, hidden log contents, hidden asset contents, invisible object existence, or private adapter staging paths.
- Success fields: `context type`, `credential source`, `credential scope`, `project id`, `exp id`, `mode`, repeated `next`.
- Success fields per `help_command`: `command`, `available`, `locked reason`, `unlock hint`, `capability source`, `summary`.
- Default rule: renders one `help_command` object for each available command only.
- `--all` rule: also renders locked `help_command` objects with `available: false`, safe `locked reason`, and safe `unlock hint`.
- `--explain` rule: includes `capability source` and any safe explanatory `summary`; without `--explain`, `capability source` may render as `none`.
- Exit: `0`; `2` on invalid help options; `5` on storage failure.

### Auth

`alab auth init`

- Context: Any.
- Credential: None.
- Required args: none.
- Options: `--home`.
- Conflicts: initialized home, or existing non-empty directory that is not an ALab home.
- Success fields: `home`, `home id`, `root key`, `created`.
- Exit: `0` on creation; `2` with `HOME_EXISTS` if already initialized; `5` on storage failure.
- Secret rule: prints the raw root key exactly once.

`alab auth root regenerate`

- Context: Any.
- Credential: Root.
- Required args: none.
- Options: global key options.
- Conflicts: missing initialized home.
- Success fields: `home`, `home id`, `root key`, `revoked key id`, `created key id`.
- Exit: `0`; `3` on auth failure; `5` on storage failure.
- Secret rule: prints the replacement root key exactly once.

### Config

`alab config show`

- Context: Any.
- Credential: None.
- Success fields: `home`, `schema version`, `output format`, `preview bytes`, `busy timeout ms`, `lock acquire timeout ms`, `lock heartbeat interval ms`, `lock stale after ms`, `config valid`.
- Exit: `0`; `5` on storage failure.

`alab config set <field> <toml-literal>`

- Context: Any.
- Credential: None.
- Required args: dotted `field`, TOML literal `value`.
- Allowed fields: `output.format`, `output.preview_bytes`, `storage.busy_timeout_ms`, `locks.acquire_timeout_ms`, `locks.heartbeat_interval_ms`, and `locks.stale_after_ms`.
- Rule: `output.format` may only be set to the TOML string `"text"`; any other value fails with `CONFIG_INVALID`.
- Repair rule: may repair a known field in a partially valid config. If the TOML cannot be parsed, fail with a next action to use `alab config reset --all`.
- Success fields: `field`, `previous value`, `value`, `config valid`.
- Exit: `0`; `2` on invalid field or value; `5` on storage failure.

`alab config reset <field>|--all`

- Context: Any.
- Credential: None.
- Required args: exactly one field or `--all`.
- Success fields: `reset`, `field`, `value`, `config valid`.
- Exit: `0`; `2` on invalid field or selector conflict; `5` on storage failure.

`alab config validate [--refresh-capabilities]`

- Context: Any.
- Credential: None.
- Options: `--refresh-capabilities`.
- Success fields: `config valid`, repeated `capability`, `fingerprint`, `status`, `checked at`, `next`.
- Exit: `0` when valid; `2` with `CONFIG_INVALID` when invalid; `5` on storage failure.

### Keys

`alab key create --project <project_id> [--role admin]`

- Context: Any or Project.
- Credential: Root.
- Required args: `--project`.
- Defaults: `--role admin`.
- Conflicts: any role other than `admin`.
- Success fields: `project id`, `key id`, `role`, `admin key`, `created`.
- Exit: `0`; `3` on auth failure; `2` on unknown project or invalid role.
- Secret rule: prints raw admin key exactly once.

`alab key list --root`

- Context: Any.
- Credential: Root.
- Required args: `--root`.
- Conflicts: `--project`.
- Success fields per key: `key id`, `credential type`, `status`, `created at`, `revoked at`.
- Exit: `0`; `3` on auth failure.

`alab key list --project <project_id>`

- Context: Any or Project.
- Credential: Root/admin.
- Required args: `--project` unless project context supplies it.
- Conflicts: `--root`.
- Success fields per key: `project id`, `key id`, `role`, `status`, `created at`, `revoked at`.
- Exit: `0`; `3` on auth failure.

`alab key revoke <key_id> [--project <project_id>]`

- Context: Any or Project.
- Credential: Root.
- Required args: `key_id`.
- Conflicts: revoking the only active root key through this command.
- Success fields: `key id`, `status`, `revoked at`.
- Exit: `0`; `3` on auth failure; `2` if key id is unknown.

### Context

`alab context show [--path <dir>]`

- Context: Any.
- Credential: None for local marker summary; Root/admin or valid token for full matching record details.
- Defaults: `--path .`.
- Success fields: `path`, `resolved path`, `home id`, `context type`, `project id`, `exp id`, `token id`, `registered`, `path status`, `next`.
- Exit: `0`; `4` on conflict; `2` for invalid path.

`alab context repair --path <dir>`

- Context: Any.
- Credential: Root/admin, or valid self token under strict self-repair rules.
- Required args: `--path`.
- Success fields: `path`, `resolved path`, `context type`, `project id`, `exp id`, `repair mode`, `status`.
- Exit: `0`; `3` on auth failure; `4` on conflict or failed self-repair checks.

### Project

`alab project list [--include-archived]`

- Context: Any.
- Credential: Root.
- Success fields per project: `project id`, `project name`, `project status`, `created at`, `updated at`, `archived at`.
- Exit: `0`; `3` on auth failure.

`alab project show [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `project id`, `home id`, `project name`, `status`, `task`, `goal`, `active config version`, `latest attempted config version`, `default source`, `runner type`, `reward type`, `visibility scope`, `mutable summary`, `public exp create`.
- Exit: `0`; `3` on auth failure; `2` with `CONTEXT_NOT_FOUND` on missing context.

`alab project archive [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `project id`, `previous status`, `project status`, `archived at`.
- Exit: `0`; `3` on auth failure; `4` with `RESOURCE_BUSY` when active validation, source import, run, submit, worktree maintenance, or other project maintenance locks exist.

`alab project unarchive [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `project id`, `previous status`, `project status`, `unarchived at`.
- Exit: `0`; `3` on auth failure.

`alab project remove [--project <project_id>] (--dry-run|--force --confirm <project_id>) --cascade [--reason <text>]`

- Context: Project or explicit project.
- Credential: Root.
- Required args: `--cascade`, plus either `--dry-run` or both `--force` and `--confirm <project_id>`.
- Success fields: `project id`, `dry run`, `removed`, `cascade`, `audit id`, repeated deleted object counts.
- Dry run renders blockers and deletion counts without writing audit rows or deleting data.
- Cascade rule: because project remove is a whole-tree deletion operation, child project records do not need to be individually archived once the project itself is archived and active locks are absent.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` when project is not archived or cascade blockers exist.

`alab status [--project <project_id>]`

- Context: Project, Experiment, Inspection, or explicit project.
- Credential: Public safe summary, Root/admin in project context, Token in experiment/inspection context.
- Success fields vary by scope, but always include `context type`, `project id`, `project status`, `task`, `next`.
- Public status excludes history, env values, secret names/values, full runner commands, hidden assets, hidden logs, and absolute catalog/staging paths.
- Exit: `0`; `4` on context conflict; `3` when private project requires auth.

`alab project init local|git|empty|harbor|skydiscover ...`

- Context: Any.
- Credential: Root.
- Required args: `--config`, mode-specific source/task fields.
- Common options: `--name`, `--task`, `--goal`, `--config`, `--skip-baseline-test`.
- Source conflicts: exactly one source origin per init mode unless adapter source precedence explicitly says otherwise.
- Harbor and SkyDiscover init source rule: V1 rejects `--source-ref`; explicit editable sources for adapter init must be `--source-path`, `--source-git`, or `--source-empty`, or else the adapter-derived source is used.
- Adapter source rule: if an adapter-derived editable source and explicit caller source are both present, identical canonical tree hashes dedupe; different hashes fail with `SOURCE_INVALID`.
- Config source rule: if input config includes `source.default_source_ref`, it must match the staged canonical source ref; mismatch fails with `CONFIG_INVALID`.
- Runtime config rule: runner, reward, artifact, log, env, secret, Docker, Harbor, and SkyDiscover fields are read from config only. Init exposes no runtime flags in V1.
- Success fields: `project id`, `project name`, `project status`, `source id`, `source ref`, `config version`, `validation id`, `validation status`, `admin key`, `next`.
- Secret rule: always creates one project admin key when the project record is written and prints the raw admin key exactly once, including when baseline validation later fails.
- Exit: `0` when validation passes or is skipped by request; `1` when project is created but baseline fails; `2` on invalid config/source; `3` on auth failure.

`alab project config show [--project <project_id>] [--version latest-attempted|active-valid|<n>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Defaults: `--version latest-attempted`.
- Version rule: `active-valid` fails with `PROJECT_INVALID` when no active valid config exists.
- Success fields: `project id`, `config version`, `version selector`, `config hash`, `project name`, `task`, `goal`, `default source`, `runner type`, `runner working directory`, `timeout seconds`, `env mode`, `reward type`, `reward direction`, `primary metric`, `artifact glob count`, `stdout limit bytes`, `stderr limit bytes`, `mutable summary`, `visibility scope`, `public exp create`, repeated `env name`, repeated `secret name`, repeated `secret fingerprint`.
- Secret rule: never renders raw secret values.
- Exit: `0`; `3` on auth failure.

`alab project config export --out <path> [--overwrite] [--project <project_id>] [--version latest-attempted|active-valid|<n>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: `--out`.
- Defaults: `--version latest-attempted`.
- Defaults: fail if target exists.
- Conflicts: existing output path without `--overwrite`.
- Version rule: `active-valid` fails with `PROJECT_INVALID` when no active valid config exists.
- Success fields: `project id`, `config version`, `out`, `wrote`, `secret mode`.
- Exit: `0`; `2` with `OUTPUT_EXISTS` if target exists; `3` on auth failure.

`alab project config import --config <path> [--project <project_id>] [--dry-run] [--skip-baseline-test]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: `--config`.
- Conflicts: `--dry-run` with `--skip-baseline-test`.
- Dry-run rule: parses and canonicalizes input, computes the config diff, reports whether baseline would be required, and runs runtime capability checks. It does not write DB rows, create audit rows, mutate files, or execute a baseline runner.
- Success fields: `project id`, `previous active config version`, `latest attempted config version`, `runtime affecting`, `validation status`, `project status`, `next`.
- Exit: `0` on non-runtime change or passed/skipped baseline; `1` on failed baseline with record; `2` on schema invalid.

`alab project config set <field> <value> [--project <project_id>] [--dry-run] [--skip-baseline-test]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: dotted `field`, TOML literal `value`.
- Conflicts: secret fields; `[secret_env]` must use `project secret` or config import retain markers; `--dry-run` with `--skip-baseline-test`.
- Rule: edits are based on the latest attempted config, not only the active valid config. Metadata-only edits cannot make an invalid runtime config valid.
- Rule: accepts TOML literals for non-secret scalar, array, and map fields.
- Rule: setting an array or map replaces the complete field; V1 does not deep-merge nested values.
- Dry-run rule follows config import dry-run.
- Success and exit follow config import.

`alab project env set|unset|list ...`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: `set <name> <value>`, `unset <name>`, none for `list`.
- Rule: `<name>` must match `^[A-Za-z_][A-Za-z0-9_]*$`.
- Success fields: `project id`, `config version`, `env name`, `action`, `runtime affecting`, `validation status`.
- Exit follows config import for mutating commands; `list` exits `0`.

`alab project secret set|unset|list|gc ...`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: `set <name> --value-stdin|--value-file <path>`, `unset <name>`, none for `list`, exactly one of `gc --dry-run` or `gc --apply`.
- Conflicts: `--value-stdin` with `--value-file`; `gc --dry-run` with `gc --apply`.
- Rule: `<name>` must match `^[A-Za-z_][A-Za-z0-9_]*$`.
- Secret input rule: `--value-stdin` and `--value-file` read the complete input, strip at most one trailing newline, and then require a non-empty single-line UTF-8 value with no NUL bytes. Empty values, embedded newlines, and NUL bytes fail with `CONFIG_INVALID`; values shorter than 4 UTF-8 bytes fail with `CONFIG_INVALID` under the storage secret-value rule.
- Rule: `gc --dry-run` renders unreferenced secret value candidates without deleting data or writing audit rows; `gc --apply` deletes only unreferenced raw secret values and writes an audit event.
- Success fields for `set|unset`: `project id`, `config version`, `secret name`, `action`, `secret fingerprint`, `runtime affecting`, `validation status`.
- Success fields per secret for `list`: `project id`, `secret name`, `secret fingerprint`, `referenced`, `created at`, `replaced at`.
- Success fields for `gc`: `project id`, `dry run`, `deleted count`, repeated `secret value id`, `audit id`.
- Secret rule: never renders raw secret values.
- Exit follows config import for mutating commands.

`alab project validate [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `project id`, `validation id`, `config version`, `validation status`, `exit code`, `reward`, `reward parse status`, `project status`, `next`.
- Exit: `0` on pass; `1` on failed/error/timeout validation with saved record; `3` on auth failure.

`alab project validation archive|unarchive <validation_id> [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `project id`, `validation id`, `previous archive status`, `archive status`, timestamp.
- Exit: `0`; `3` on auth failure; `4` when attempting to archive active validation.

`alab project validation remove <validation_id> [--project <project_id>] (--dry-run|--force --confirm <validation_id>) [--cascade] [--reason <text>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: either `--dry-run` or both `--force` and matching `--confirm`.
- Success fields: `project id`, `validation id`, `dry run`, `removed`, `audit id`.
- Dry run renders blockers and deletion counts without writing audit rows or deleting data.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` when validation is not archived, is active, or cascade blockers exist.

`alab project locks clear-stale [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `project id`, `cleared count`, repeated `lock name` when any are cleared.
- Exit: `0`; `3` on auth failure.

`alab backup prune (--keep <n>|--older-than <days>)`

- Context: Any.
- Credential: Root.
- Required args: exactly one of `--keep` or `--older-than`.
- Success fields: `backup pruned count`, repeated `backup path` when any are pruned, `audit id`.
- Exit: `0`; `2` on invalid retention options; `3` on auth failure.

### Audit

`alab audit list [--project <project_id>] [--object-type <type>] [--object-id <id>] [--action <action>] [--actor <credential_id>] [--created-after <time>] [--created-before <time>] [--limit <n>] [--offset <n>]`

- Context: Any or Project.
- Credential: Root globally, or Root/admin when scoped to a project.
- Defaults: `--limit 50`, `--offset 0`.
- Action filter values are the generic audit actions: `add`, `update`, `archive`, `unarchive`, `remove`, `restore`, `repair`, `revoke`, `regenerate`, `prune`, `gc`, and `clear`.
- Success fields per event: `audit id`, `project id`, `exp id`, `actor type`, `actor credential id`, `action`, `object type`, `object id`, `cascade`, `reason`, `created at`.
- Exit: `0`; `3` on auth failure; `2` on invalid filters.

`alab audit show <audit_id> [--project <project_id>]`

- Context: Any or Project.
- Credential: Root globally, or Root/admin when scoped to the event's project.
- Audit output uses generic `action` plus `object type`; special action names such as `catalog_remove`, `worktree_remove`, and `checkout_remove` are not valid V1 output.
- Success fields: `audit id`, `project id`, `exp id`, `actor type`, `actor credential id`, `action`, `object type`, `object id`, `cascade`, `reason`, `deleted ids`, sanitized `metadata`, `created at`.
- Exit: `0`; `2` if not found or outside project scope; `3` on auth failure.

### Source

`alab source import ...`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: exactly one of `--source-path`, `--source-git`, `--source-empty`.
- Options: `--source-subdir`, `--name`, import limits.
- Conflicts: multiple source origins; `--source-subdir` with `--source-empty`.
- Success fields: `project id`, `source id`, `source ref`, `source name`, `tree hash`, `deduped`, warnings.
- Exit: `0`; `2` on source invalid, limit exceeded, or name conflict; `3` on auth failure.

`alab source list [--project <project_id>] [--include-archived]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields per source: `source id`, `source ref`, `source name`, `status`, `tree hash`, `created at`, `archived at`.
- Exit: `0`; `3` on auth failure.

`alab source show <source_id> [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `source id`, `source ref`, `source name`, `status`, `source commit`, `tree hash`, `origin type`, `origin summary`.
- Exit: `0`; `2` if not found; `3` on auth failure.

`alab source archive|unarchive <source_id> [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Success fields: `source id`, `previous status`, `source status`, timestamp.
- Exit: `0`; `4` with `RESOURCE_BUSY` if archiving active default source; `3` on auth failure.

`alab source remove <source_id> [--project <project_id>] (--dry-run|--force --confirm <source_id>) [--cascade] [--reason <text>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: either `--dry-run` or both `--force` and matching `--confirm`.
- Success fields: `source id`, `dry run`, `removed`, `cascade`, `audit id`, repeated blocker fields when blocked.
- Dry run renders blockers and deletion counts without writing audit rows or deleting data.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` when source is not archived, any project config version references the source, or cascade blockers exist.

### Catalog

`alab catalog skydiscover add|update [--origin-url <url>] [--ref <ref>|--commit <sha>]`

- Context: Any.
- Credential: Root.
- Options: `--origin-url`, exactly zero or one of `--ref` and `--commit`.
- Defaults: official SkyDiscover repository URL and upstream `main` resolved to an exact commit.
- Success fields: `catalog`, `origin url`, `requested ref`, `pinned commit`, `local path`, `retrieved at`, `status`, `audit id`.
- Exit: `0`; `2` on existing catalog for add, dirty catalog for update, invalid origin, invalid ref, or invalid commit; `3` on auth failure.

`alab catalog skydiscover show`

- Context: Any.
- Credential: Root.
- Success fields: `catalog`, `origin url`, `pinned commit`, `local path`, `retrieved at`, `status`.
- `show` must not fetch from the network.
- Exit: `0`; `2` when no active catalog exists; `3` on auth failure.

`alab catalog skydiscover remove --force --confirm skydiscover [--reason <text>]`

- Context: Any.
- Credential: Root.
- Required args: `--force --confirm skydiscover`.
- Success fields: `catalog`, `removed`, `audit id`.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` when active configs or any open experiment bound config reference the catalog.

### Cache

`alab cache prune [--docker-images] [--skydiscover-envs] [--trash --older-than <days>|--trash-all] [--all]`

- Context: Any.
- Credential: Root.
- Options: at least one cache selector.
- Conflicts: top-level `--all` with `--docker-images`, `--skydiscover-envs`, `--trash`, or `--trash-all`. `--trash` requires `--older-than <days>`. `--trash-all` deletes all trash entries. Top-level `--all` includes Docker image cache, SkyDiscover env cache, and all trash entries.
- Success fields: `cache pruned count`, repeated `cache kind`, `audit id`.
- Exit: `0`; `2` on invalid selector combination; `3` on auth failure.

### Experiment And Worktree

`alab exp create ...`

- Context: Project or explicit project.
- Credential: Public when enabled, otherwise Root/admin.
- Required args: `--name`; source origin optional and defaults to project default source.
- Source conflicts: at most one of `--source-ref`, `--source-path`, `--source-git`, `--source-empty`, `--from-exp`.
- Options: `--goal`, `--path`, repeated `--tag`, `--git-ref`, `--source-subdir`, `--from-commit`, mutable/visibility narrowing.
- Public no-key `--from-exp` uses public inheritance visibility: current project public policy intersected with the source experiment's stored visibility upper bound.
- Public no-key `--source-git` may use local non-interactive Git credential helpers and renders `PUBLIC_GIT_CREDENTIAL_HELPER_USED` when applicable. Git credential prompts are disabled.
- Success fields: `project id`, `exp id`, `experiment name`, `source id`, `branch`, `worktree path`, `token path`, `config version`, `next`.
- Exit: `0`; `2` on invalid source/name/path; `3` when auth required; `4` on invalid project status.

`alab exp archive|unarchive <exp_id> [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Options: none beyond explicit project selection.
- Success fields: `exp id`, `previous status`, `experiment status`, timestamp.
- Exit: `0`; `4` on active lock; `3` on auth failure.

`alab exp remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--cascade] [--reason <text>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: either `--dry-run` or both `--force` and matching `--confirm`.
- Success fields: `exp id`, `dry run`, `removed`, `cascade`, `audit id`, repeated deleted object counts or blockers.
- Dry run renders blockers and deletion counts without writing audit rows or deleting data.
- Cascade rule: because experiment remove is a whole-experiment deletion operation, child run, artifact, log, annotation, tag, inspection, worktree, and submission records do not need to be individually archived once the experiment itself is archived and active run/submit locks are absent.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` when experiment is not archived or cascade blockers exist.

`alab exp checkout <exp_id> --path <dir> [--commit final|latest|best|<sha>]`

- Context: Project or explicit project.
- Credential: Root/admin or visible token.
- Required args: `--path`.
- Success fields: `exp id`, `inspection path`, `inspection commit`, `token path`, `token id`, `next`.
- Exit: `0`; `2` on invalid path/commit; `3` on auth failure.

`alab exp checkout remove (--token-id <token_id>|--path <dir>) [--project <project_id>] (--dry-run|--force --confirm <token_id-or-path-hash>) [--reason <text>]`

- Context: Project, Experiment, Inspection, or explicit project.
- Credential: Root/admin for any inspection checkout, or matching inspection token for its own checkout.
- Required args: exactly one of `--token-id` or `--path`, plus either `--dry-run` or both `--force` and matching `--confirm`.
- Success fields: `exp id`, `inspection path`, `token id`, `dry run`, `removed`, `token revoked`, `audit id`.
- Rule: if the registered filesystem path is already missing, actual remove reconciles DB state, revokes the inspection token, writes an audit event, and exits `0`.
- Exit: `0`; `2` on invalid selector or confirmation; `3` on auth failure; `4` on scope failure.

`alab exp worktree remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--reason <text>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: either `--dry-run` or both `--force` and matching `--confirm`.
- Success fields: `exp id`, `old worktree path`, `worktree state`, `dry run`, `removed`, `token revoked`, `audit id`.
- Rule: if the registered filesystem path is already missing, actual remove reconciles DB state, revokes the active worktree token, writes an audit event, and exits `0`.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` on filesystem cleanup failure.

`alab exp worktree restore <exp_id> --path <dir> [--project <project_id>]`

- Context: Project or explicit project.
- Credential: Root/admin.
- Required args: `--path`.
- Success fields: `exp id`, `branch`, `worktree path`, `worktree state`, `token path`, `revoked token id`, `new token id`.
- Exit: `0`; `2` on invalid path; `3` on auth failure.

`alab exp token list|revoke|regenerate <exp_id> ...`

- Context: Project or explicit project.
- Credential: Root/admin.
- Options: `--token-id`, `--mode worktree|inspection`, `--all`.
- Conflicts: `--all` with `--token-id` or `--mode`.
- Defaults: worktree token when no selector is supplied.
- Success fields per token for `list`: `project id`, `exp id`, `token id`, `token mode`, `status`, `path status`, `created at`, `revoked at`.
- Success fields for `revoke`: `project id`, `exp id`, `token id`, `token mode`, `status`, `revoked at`.
- Success fields for `regenerate`: `project id`, `exp id`, `revoked token id`, `new token id`, `token mode`, `token path`, `created at`.
- Secret rule: regenerate writes the raw token to the registered path and never prints it.
- Exit: `0`; `3` on auth failure.

`alab exp tag add|remove|list <exp_id> ...`

- Context: Experiment or Project.
- Credential: owning worktree token for own experiment, or Root/admin.
- Required args: tag for add/remove.
- Success fields: `exp id`, `tag`, `action`, `tags`.
- Exit: `0`; `3` on auth failure; `4` on scope failure.

### Run And Submit

`alab run --message <message>`

- Context: Experiment.
- Credential: valid worktree token.
- Required args: `--message`.
- Success fields: `run id`, `exp id`, `commit`, `created commit`, `run status`, `exit code`, `reward`, `reward parse status`, `stdout preview`, `stderr preview`, `artifact count`, `warning code`, `next`.
- Exit: `0` on passed run; `1` on failed/error/timeout run with saved record; `4` on scope or state failure.

`alab submit --message <message> --summary <text>|--summary-file <path> --feedback <text>|--feedback-file <path> --ref <exp_id|none> [--ref <exp_id> ...] [--rerun]`

- Context: Experiment.
- Credential: valid worktree token.
- Required args: message, exactly one summary input, exactly one feedback input, at least one ref.
- Conflicts: direct summary with summary file; direct feedback with feedback file; `--ref none` with any experiment ref.
- State rule: project must not be archived, experiment must be open, and experiment worktree state must be active.
- Path rule: summary and feedback files resolve relative to the current command cwd.
- Ref rule: refs are deduplicated preserving first-seen order.
- Success fields: `exp id`, `submit accepted`, `final run id`, `final commit`, `experiment status`, `summary stored`, `feedback stored`, repeated `ref`.
- Exit: `0` when accepted; `1` when final run is not passed or reusable run is missing; `4` on scope/state failure.

### Observe And Aliases

`alab observe experiments list|search|show|best ...`

- Context: Project, Experiment, or Inspection.
- Credential: Root/admin in project context; token visibility in experiment/inspection context.
- Required args: `search --query`, `show <exp_id>`.
- Success fields per experiment: `project id`, `exp id`, `experiment name`, `experiment status`, `source id`, `source ref`, repeated `tag`, `latest run id`, `latest commit`, `final run id`, `final commit`, `best run id`, `reward`, `reward parse status`, `created at`, `updated at`, `closed at`, `archived at`.

`alab observe runs list|show|archive|unarchive|remove ...`

- Context and credential: same as observe experiments.
- Required args: `show <run_id>`, `archive <run_id>`, `unarchive <run_id>`, or `remove <run_id> (--dry-run|--force --confirm <run_id>)`.
- Options: `remove` accepts `--cascade`, `--reason`, and `--dry-run`.
- Success fields per run: `run id`, `exp id`, `commit`, `run status`, `exit code`, `reward`, `reward parse status`, `config version`, `stdout preview`, `stderr preview`, `artifact count`, `log count`, `hidden log available`, `started at`, `ended at`, repeated `warning code`.
- Lifecycle success fields include previous archive status, archive status, removed, and audit id.
- Credential: owning worktree token may archive/unarchive its own experiment runs; remove requires Root/admin.

`alab observe artifacts list|show|export|archive|unarchive|remove ...`

- Context and credential: same as observe experiments.
- Required args: `show <artifact_id>`, `export <artifact_id> --out <path>`, `archive <artifact_id>`, `unarchive <artifact_id>`, or `remove <artifact_id> (--dry-run|--force --confirm <artifact_id>)`.
- Options: export accepts `--overwrite` and `--include-archived`; remove accepts `--cascade`, `--reason`, and `--dry-run`.
- Success fields per artifact: `artifact id`, `exp id`, `run id`, `validation id`, `root`, `path`, `status`, `archive status`, `size bytes`, `content hash`, `created at`, `out`.
- Exit: `2` with `OUTPUT_EXISTS` if export target exists without `--overwrite`.
- Archived artifacts can be shown by id when authorized. Exporting archived artifacts requires `--include-archived`.
- Credential: owning worktree token may archive/unarchive own experiment artifacts; remove requires Root/admin.

`alab observe logs list|show|export|archive|unarchive|remove ...`

- Context and credential: same as observe experiments; hidden logs require Root/admin plus explicit `--include-hidden`.
- Required args: `show <log_id>`, `export <log_id> --out <path>`, `archive <log_id>`, `unarchive <log_id>`, or `remove <log_id> (--dry-run|--force --confirm <log_id>)`.
- Options: show/export accept `--include-hidden`; export accepts `--include-archived`; remove accepts `--cascade`, `--reason`, and `--dry-run`.
- Success fields per log: `log id`, `exp id`, `run id`, `validation id`, `stream`, `size bytes`, `stored bytes`, `truncated`, `hidden`, `archive status`, `preview`, `out`, `audit id`.
- Archived logs can be shown by id, including log text, when authorized. Exporting archived logs requires `--include-archived`.
- Credential: owning worktree token may archive/unarchive own visible logs; hidden log lifecycle and remove require Root/admin.

`alab observe annotations list|show ...`

- Context and credential: same as observe experiments.
- Required args: `show <annotation_id>`.
- Options: `--history`.
- Success fields per annotation: `annotation id`, `target type`, `target id`, `resolved commit`, `status`, `current revision`, `visibility`, `author`, `body`, `created at`, `updated at`, repeated `revision`.

### Annotation Mutation

`alab annotate add --target <target> --body <text>|--body-file <path> [--author <label>] [--private] [--private-to-exp <exp_id>]`

- Context: Experiment or Project.
- Credential: visible token, or Root/admin.
- Required args: target and exactly one body input.
- Conflicts: `--body` with `--body-file`; token context with `--private-to-exp`.
- Success fields: `annotation id`, `target type`, `target id`, `resolved commit`, `revision`, `visibility`, `created at`.
- Exit: `0`; `2` on invalid target; `3` on auth failure; `4` on visibility failure.

`alab annotate edit <annotation_id> --body <text>|--body-file <path> [--author <label>]`

- Context: Experiment or Project.
- Credential: creating token for its annotation, or Root/admin.
- Required args: annotation id and exactly one body input.
- Success fields: `annotation id`, `revision`, `updated at`.
- Exit: `0`; `3` on auth failure; `4` on scope failure.

`alab annotate archive <annotation_id>`

- Context: Experiment or Project.
- Credential: creating token for its annotation, or Root/admin.
- Success fields: `annotation id`, `previous status`, `annotation status`, `archived at`.
- Exit: `0`; `3` on auth failure; `4` on scope failure.

`alab annotate unarchive <annotation_id>`

- Context: Experiment or Project.
- Credential: creating token for its annotation, or Root/admin.
- Success fields: `annotation id`, `previous status`, `annotation status`, `unarchived at`.
- Exit: `0`; `3` on auth failure; `4` on scope failure.

`alab annotate remove <annotation_id> (--dry-run|--force --confirm <annotation_id>) [--reason <text>]`

- Context: Experiment or Project.
- Credential: creating token for its annotation, or Root/admin.
- Required args: either `--dry-run` or both `--force` and matching `--confirm`.
- Success fields: `annotation id`, `dry run`, `removed`, `audit id`.
- Dry run renders blockers and deletion counts without writing audit rows or deleting data.
- Exit: `0`; `2` on missing or wrong confirmation; `3` on auth failure; `4` when annotation is not archived or scope fails.
