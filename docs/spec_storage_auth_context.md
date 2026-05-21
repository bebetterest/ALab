# ALab V1 Storage, Auth, And Context Spec

This spec defines ALab home state, SQLite storage, credential storage, context detection, config persistence, migrations, and backup behavior.

## 1. Home Identity And Layout

Default ALab home:

```text
~/.ALab
```

Home resolution priority is `--home`, then `ALAB_HOME`, then `~/.ALab`.

`alab auth init` generates one stable home id:

```text
home-<random_suffix>
```

Rules:

- The suffix carries at least 128 bits of entropy.
- The home id is stored in SQLite and written into every `.alab/context.json`.
- Context detection and repair fail closed when a marker `home_id` does not match the active ALab home.
- The home id is not a secret and must not be used for authorization.

`alab auth init` target path rules:

- If the resolved home path does not exist, ALab creates it and initializes the standard layout.
- If the resolved home path exists and is an empty directory, ALab initializes it.
- If the resolved home path exists and is not empty but is not an initialized ALab home, `auth init` fails with `HOME_EXISTS`.
- If the resolved home path already contains an initialized ALab database or context state, `auth init` fails with `HOME_EXISTS`.
- `auth init` must not merge with, overwrite, or clean up unrelated files in a non-empty directory.

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
└── tmp/
```

There is no `records/` directory in V1. SQLite is authoritative for structured records. Logs and artifact bytes are plaintext files referenced by SQLite.

Project workspace directories under `project-workspaces/` are marker-only control directories for project-scoped CLI context. They are not source checkouts and must not be used as editable experiment worktrees. Experiment worktrees are registered external paths. The default experiment worktree path is `./<project_id>_<exp_id>` relative to the command cwd when `exp create` omits `--path`. That cwd may be a project control context, but it is not required to be one; any cwd that passes path registration and nesting checks is valid.

## 2. SQLite Rules

ALab uses standard-library SQLite with these startup pragmas:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = <configured milliseconds>;
```

Rules:

- Command flows use short write transactions.
- Long-running work such as source scanning, Git operations, runner execution, Docker build/run, artifact hashing, and log capture must not hold an open SQLite write transaction.
- Different experiments may run concurrently.
- A single experiment's run/submit path is serialized by the `locks` table.
- Typed columns store query-critical fields.
- `*_json` columns store canonical JSON for complete structured details.
- Canonical JSON uses sorted keys, UTF-8, no insignificant whitespace, stable enum strings, and no non-finite numeric values.
- Every persisted JSON object has a `schema_version` integer and a documented key set. Unknown keys fail validation unless that JSON contract explicitly reserves an extension object.
- Datetimes are UTC RFC 3339 strings with `Z`.
- IDs are opaque. Authorization never derives from id prefixes.
- CLI object id parameters require complete ALab ids. Git commit selectors are the only identifiers that may accept a full or unambiguous abbreviated SHA.
- Public ids use a type prefix plus random high-entropy suffix for readability, such as `proj-...`, `src-...`, `exp-...`, `run-...`, `val-...`, `art-...`, `log-...`, and `ann-...`.
- Public ids use `<type>-<slug_hint>-<random_suffix>` when a human name is available and `<type>-<random_suffix>` otherwise. The random suffix is a 22-character unpadded base64url string carrying 128 bits of entropy.
- Slug hints use NFKC normalization, lowercase ASCII, runs of non-`a-z0-9` characters collapsed to `-`, leading/trailing `-` removed, and the type name when the result is empty.
- Path hashes use `sha256:<lowercase_hex>` over the normalized resolved realpath bytes after platform case normalization has been applied.
- SQLite foreign keys use restrict-style behavior for authoritative records that are not retained after parent removal. Implementation should use real foreign keys for authoritative parent-child relationships whose parents cannot be hard-removed while retained children still reference them. Application code performs explicit dependency checks, writes audit rows, and then deletes rows in a controlled order for hard remove flows.
- Retained diagnostic and audit tables store denormalized object ids where needed and must not require foreign keys to rows that hard remove can delete. This includes `audit_events`, retained revoked `credentials`, removed `path_registry` rows, and cache/catalog metadata kept only for cleanup or audit.

Plaintext data may include project names, tasks, config summaries, experiment names, tags, summaries, feedback, annotations, logs, reward values, metrics, artifact metadata and bytes, local paths, source refs, branch names, commit hashes, content hashes, and `secret_env` values.

## 3. DDL-Level Schema Contract

Implementation may add internal columns, but these tables, constraints, indexes, and nullability rules are part of V1. This section is a logical DDL contract, not a literal migration SQL file; migration SQL must implement at least these externally observable constraints and indexes without weakening the documented behavior.

### `homes`

Columns:

- `home_id TEXT PRIMARY KEY`
- `schema_version INTEGER NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Constraints:

- exactly one row is active in V1.
- `home_id` starts with `home-`.

### `schema_migrations`

Columns:

- `version INTEGER PRIMARY KEY`
- `name TEXT NOT NULL`
- `checksum TEXT NOT NULL`
- `applied_at TEXT NOT NULL`

Indexes:

- primary key on `version`.

### `audit_events`

Columns:

- `audit_id TEXT PRIMARY KEY`
- `project_id TEXT NULL`
- `exp_id TEXT NULL`
- `actor_credential_id TEXT NULL`
- `actor_type TEXT NOT NULL`
- `action TEXT NOT NULL`
- `object_type TEXT NOT NULL`
- `object_id TEXT NOT NULL`
- `cascade INTEGER NOT NULL`
- `reason TEXT NULL`
- `deleted_ids_json TEXT NOT NULL`
- `metadata_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Checks:

- `actor_type IN ('root','admin','token','system')`
- `action IN ('add','update','archive','unarchive','remove','restore','repair','revoke','regenerate','prune','gc','clear')`
- `object_type IN ('project','source','experiment','run','validation','artifact','log','annotation','credential','secret_value','cache','backup','catalog','lock','worktree','inspection_checkout')`
- `cascade IN (0,1)`
- `reason` is null or valid UTF-8 text no longer than 65536 bytes after encoding.
- `deleted_ids_json` and `metadata_json` are canonical JSON and must not contain raw secrets, verifier hashes, hidden asset contents, or raw hidden logs.

Indexes:

- index on `(project_id, created_at)`.
- index on `(project_id, exp_id, created_at)`.
- index on `(object_type, object_id)`.
- index on `(actor_credential_id, created_at)`.

Hard-removed authoritative rows do not retain row-local `removed_at` fields because the rows are deleted. Removal actor, time, cascade flag, deleted ids, and sanitized metadata are authoritative in `audit_events`.

Audit action model:

- `action` is a generic lifecycle verb. `object_type` identifies the operated object, such as `project`, `source`, `experiment`, `run`, `validation`, `artifact`, `log`, `annotation`, `credential`, `secret_value`, `cache`, `backup`, `catalog`, `lock`, `worktree`, or `inspection_checkout`.
- Historical special action names such as `catalog_remove`, `worktree_remove`, `worktree_restore`, and `checkout_remove` are not valid V1 action values. They are represented by generic `action` plus specific `object_type`.

### `credentials`

Columns:

- `credential_id TEXT PRIMARY KEY`
- `credential_type TEXT NOT NULL`
- `project_id TEXT NULL`
- `exp_id TEXT NULL`
- `token_mode TEXT NULL`
- `registered_path_hash TEXT NULL`
- `status TEXT NOT NULL`
- `salt BLOB NOT NULL`
- `verifier_hash BLOB NOT NULL`
- `created_at TEXT NOT NULL`
- `revoked_at TEXT NULL`
- `metadata_json TEXT NOT NULL`

Checks:

- `credential_type IN ('root','admin','token')`
- `status IN ('active','revoked')`
- root credentials have null `project_id`, `exp_id`, `token_mode`, and `registered_path_hash`.
- admin credentials have non-null `project_id`, null `exp_id`, null `token_mode`, and null `registered_path_hash`.
- token credentials have non-null `project_id`, non-null `exp_id`, `token_mode IN ('worktree','inspection')`, and non-null `registered_path_hash`.

Indexes:

- unique partial index for one active root credential.
- index on `(project_id, credential_type, status)`.
- index on `(project_id, exp_id, token_mode, status)`.
- unique active worktree token per experiment: `(exp_id)` where `credential_type='token' AND token_mode='worktree' AND status='active'`.

### `projects`

Columns:

- `project_id TEXT PRIMARY KEY`
- `status TEXT NOT NULL`
- `pre_archive_status TEXT NULL`
- `canonical_repo_path TEXT NOT NULL`
- `control_path TEXT NOT NULL`
- `secret_fingerprint_key BLOB NOT NULL`
- `latest_attempted_config_version INTEGER NULL`
- `active_valid_config_version INTEGER NULL`
- `active_validation_id TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `archived_at TEXT NULL`

Checks:

- `status IN ('valid','invalid','archived')`
- `pre_archive_status IN ('valid','invalid')` when status is `archived`; otherwise null.
- `secret_fingerprint_key` is generated once at project creation, is never exported, and is used only to compute project-scoped HMAC fingerprints for `secret_env` retain markers and secret summaries.

Indexes:

- unique index on `canonical_repo_path`.
- unique index on `control_path`.
- index on `(status, updated_at)`.

### `project_config_versions`

Columns:

- `project_id TEXT NOT NULL`
- `version INTEGER NOT NULL`
- `canonical_config_json TEXT NOT NULL`
- `config_hash TEXT NOT NULL`
- `baseline_required INTEGER NOT NULL`
- `validation_status TEXT NOT NULL`
- `inherited_from_validation_id TEXT NULL`
- `created_at TEXT NOT NULL`
- `created_by_credential_id TEXT NULL`

Primary key:

- `(project_id, version)`

Checks:

- `validation_status IN ('running','passed','failed','error','timeout','skipped','inherited','interrupted')`
- `baseline_required IN (0,1)`
- `inherited_from_validation_id` is required when `validation_status='inherited'` and null otherwise.

Indexes:

- index on `(project_id, validation_status)`.
- index on `(project_id, config_hash)`.

Version rules:

- Versions are monotonic per project.
- If an imported or edited config is byte-identical by `config_hash` to `latest_attempted_config_version`, the command is a no-op and does not create a new version.
- If a config matches an older version but differs from the latest attempted version, ALab creates a new version with the same canonical config content and a new monotonic version number.
- `config_hash` is not unique in V1.

Config edit rule:

- Import, set, env, and secret changes are based on `latest_attempted_config_version`.
- A metadata-only change cannot make an invalid runtime config valid.
- Schema-invalid changes are not written.

### `secret_values`

Columns:

- `secret_value_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `name TEXT NOT NULL`
- `value TEXT NOT NULL`
- `fingerprint TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `created_by_credential_id TEXT NULL`
- `replaced_at TEXT NULL`

Checks:

- `value` is valid UTF-8 text, does not contain NUL, and is at least 4 bytes after UTF-8 encoding.
- `fingerprint` uses project-specific HMAC and starts with `hmac-sha256:`.

Indexes:

- index on `(project_id, name, created_at)`.
- index on `(project_id, fingerprint)`.

### `sources`

Columns:

- `source_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `name TEXT NOT NULL`
- `name_slug TEXT NOT NULL`
- `source_ref TEXT NOT NULL`
- `source_commit TEXT NOT NULL`
- `tree_hash TEXT NOT NULL`
- `status TEXT NOT NULL`
- `origin_metadata_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `archived_at TEXT NULL`

Checks:

- `status IN ('active','archived')`
- `source_ref = 'alab/source/' || source_id`

Indexes:

- unique index on `(project_id, name_slug)`.
- unique index on `(project_id, source_ref)`.
- unique partial index on `(project_id, tree_hash)` where `status='active'` for active dedupe lookup.
- index on `(project_id, status)`.

### `experiments`

Columns:

- `exp_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `source_id TEXT NOT NULL`
- `bound_config_version INTEGER NOT NULL`
- `bound_validation_id TEXT NOT NULL`
- `baseline_commit TEXT NOT NULL`
- `branch_name TEXT NOT NULL`
- `worktree_path TEXT NULL`
- `worktree_path_hash TEXT NULL`
- `worktree_state TEXT NOT NULL`
- `status TEXT NOT NULL`
- `pre_archive_status TEXT NULL`
- `metadata_json TEXT NOT NULL`
- `policy_json TEXT NOT NULL`
- `latest_run_id TEXT NULL`
- `latest_commit TEXT NULL`
- `final_run_id TEXT NULL`
- `final_commit TEXT NULL`
- `final_run_removed_at TEXT NULL`
- `final_run_removed_by TEXT NULL`
- `final_run_removed_audit_id TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `closed_at TEXT NULL`
- `archived_at TEXT NULL`

Checks:

- `worktree_state IN ('active','removed')`
- `status IN ('open','closed','archived')`
- `pre_archive_status IN ('open','closed')` when status is `archived`; otherwise null.
- `closed_at` is non-null only when status is `closed` or archived from closed.
- `final_run_removed_at`, `final_run_removed_by`, and `final_run_removed_audit_id` are either all null or all non-null.

Indexes:

- unique index on `(project_id, branch_name)`.
- unique index on `(project_id, json_extract(metadata_json,'$.name_slug'))`.
- index on `(project_id, status, updated_at)`.
- index on `(project_id, source_id)`.
- index on `(project_id, bound_validation_id)`.

### `experiment_submissions`

Columns:

- `submission_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `exp_id TEXT NOT NULL`
- `final_run_id TEXT NOT NULL`
- `final_commit TEXT NOT NULL`
- `message TEXT NOT NULL`
- `summary TEXT NOT NULL`
- `feedback TEXT NOT NULL`
- `refs_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `created_by_credential_id TEXT NOT NULL`

Checks:

- `refs_json` is canonical JSON with `schema_version = 1` and ordered `refs` entries.
- `message` is valid UTF-8 text no longer than 300 bytes after encoding.
- `summary` and `feedback` are valid UTF-8 text no longer than 65536 bytes each after encoding.

Indexes:

- unique index on `(exp_id)`.
- index on `(project_id, created_at)`.
- index on `(project_id, final_run_id)`.

Rules:

- Only accepted final submissions are stored.
- Failed submit attempts do not create submission rows; their run records remain authoritative.
- Submission rows have no independent archive or remove lifecycle and are removed only with their experiment.

### `experiment_tags`

Columns:

- `project_id TEXT NOT NULL`
- `exp_id TEXT NOT NULL`
- `tag_slug TEXT NOT NULL`
- `created_by_type TEXT NOT NULL`
- `created_by_id TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Primary key:

- `(exp_id, tag_slug)`

Checks:

- `created_by_type IN ('root','admin','token')`
- `tag_slug` is a normalized lowercase ASCII slug no longer than 64 bytes.

Indexes:

- index on `(project_id, tag_slug)`.
- index on `(project_id, exp_id)`.

### `runs`

Columns:

- `run_id TEXT PRIMARY KEY`
- `exp_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `commit_sha TEXT NOT NULL`
- `config_version INTEGER NOT NULL`
- `status TEXT NOT NULL`
- `exit_code INTEGER NULL`
- `reward_value REAL NULL`
- `reward_parse_status TEXT NOT NULL`
- `archive_status TEXT NOT NULL`
- `archived_at TEXT NULL`
- `unarchived_at TEXT NULL`
- `started_at TEXT NOT NULL`
- `ended_at TEXT NULL`
- `rolled_back_auto_commit TEXT NULL`
- `record_json TEXT NOT NULL`

Checks:

- `status IN ('running','passed','failed','error','timeout','interrupted')`
- `reward_parse_status IN ('not_attempted','parsed','missing','invalid','error')`
- `archive_status IN ('active','archived')`
- `archived_at` is non-null only when `archive_status='archived'`.
- `ended_at` is null only while status is `running`.
- `exit_code` may be null for runner start errors and interrupted records.

Indexes:

- index on `(project_id, exp_id, started_at)`.
- index on `(project_id, commit_sha)`.
- index on `(project_id, status)`.
- index on `(project_id, archive_status)`.
- index on `(project_id, reward_value)`.

Same commit rule:

- The same `commit_sha` may have multiple run records.
- No unique constraint may prevent repeated runs for the same commit and config version.
- Hard removal deletes run rows only after the run is archived and records the deletion in `audit_events`.

### `project_validations`

Columns:

- `validation_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `config_version INTEGER NOT NULL`
- `source_ref TEXT NOT NULL`
- `source_commit TEXT NOT NULL`
- `status TEXT NOT NULL`
- `exit_code INTEGER NULL`
- `reward_value REAL NULL`
- `reward_parse_status TEXT NOT NULL`
- `archive_status TEXT NOT NULL`
- `archived_at TEXT NULL`
- `unarchived_at TEXT NULL`
- `started_at TEXT NOT NULL`
- `ended_at TEXT NULL`
- `record_json TEXT NOT NULL`

Checks and indexes mirror `runs` where applicable.

Additional lifecycle rules:

- A row referenced by `projects.active_validation_id` cannot be archived or removed.
- Hard removal deletes validation rows only after the validation is archived and records the deletion in `audit_events`.

### `artifacts`

Columns:

- `artifact_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `exp_id TEXT NULL`
- `run_id TEXT NULL`
- `validation_id TEXT NULL`
- `root TEXT NOT NULL`
- `relative_path TEXT NOT NULL`
- `size_bytes INTEGER NULL`
- `content_hash TEXT NULL`
- `status TEXT NOT NULL`
- `archive_status TEXT NOT NULL`
- `blob_path TEXT NULL`
- `capture_error TEXT NULL`
- `archived_at TEXT NULL`
- `unarchived_at TEXT NULL`
- `created_at TEXT NOT NULL`

Checks:

- `root IN ('workspace','run')`
- `status IN ('captured','skipped','error')`
- `archive_status IN ('active','archived')`
- exactly one owner is set: `run_id` or `validation_id`.
- `size_bytes` is null or non-negative.
- Captured rows require non-null `blob_path`, `content_hash`, and `size_bytes`; non-captured rows have null `blob_path`.
- `capture_error` is non-null only when `status='error'`, and error rows require it.
- `archived_at` is non-null only when `archive_status='archived'`.

Indexes:

- index on `(project_id, exp_id, run_id)`.
- index on `(project_id, validation_id)`.
- index on `(project_id, content_hash)`.
- index on `(project_id, status)`.
- index on `(project_id, archive_status)`.

### `log_streams`

Columns:

- `log_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `exp_id TEXT NULL`
- `run_id TEXT NULL`
- `validation_id TEXT NULL`
- `stream TEXT NOT NULL`
- `size_bytes INTEGER NOT NULL`
- `stored_bytes INTEGER NOT NULL`
- `content_hash TEXT NOT NULL`
- `truncated INTEGER NOT NULL`
- `hidden INTEGER NOT NULL`
- `archive_status TEXT NOT NULL`
- `file_path TEXT NOT NULL`
- `preview_text TEXT NULL`
- `archived_at TEXT NULL`
- `unarchived_at TEXT NULL`
- `created_at TEXT NOT NULL`

Checks:

- `stream IN ('stdout','stderr','hidden_stdout','hidden_stderr')`
- `size_bytes` and `stored_bytes` are non-negative, and `stored_bytes <= size_bytes`.
- `truncated IN (0,1)` and `hidden IN (0,1)`.
- hidden streams require `hidden=1`.
- visible streams require `hidden=0`.
- `archive_status IN ('active','archived')`
- exactly one owner is set: `run_id` or `validation_id`.
- `archived_at` is non-null only when `archive_status='archived'`.

Indexes:

- index on `(project_id, exp_id, run_id)`.
- index on `(project_id, validation_id)`.
- index on `(project_id, hidden)`.
- index on `(project_id, archive_status)`.

### `annotations` And `annotation_revisions`

`annotations` columns:

- `annotation_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `target_type TEXT NOT NULL`
- `target_id TEXT NOT NULL`
- `target_json TEXT NOT NULL`
- `resolved_commit TEXT NULL`
- `current_revision INTEGER NOT NULL`
- `visibility_json TEXT NOT NULL`
- `status TEXT NOT NULL`
- `created_by_type TEXT NOT NULL`
- `created_by_id TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Checks:

- `target_type IN ('experiment','run','artifact','path','lines')`
- `status IN ('active','archived')`
- `created_by_type IN ('root','admin','token')`
- `current_revision >= 1`
- `resolved_commit` is non-null for path and lines targets.
- `target_json` is canonical JSON with `schema_version = 1` and stores the resolved experiment id, commit, repo path, and line range when applicable.

`annotation_revisions` columns:

- `annotation_id TEXT NOT NULL`
- `revision INTEGER NOT NULL`
- `body TEXT NOT NULL`
- `author_label TEXT NULL`
- `created_at TEXT NOT NULL`
- `created_by_type TEXT NOT NULL`
- `created_by_id TEXT NOT NULL`

Primary key:

- `(annotation_id, revision)`

Checks:

- `revision >= 1`
- `created_by_type IN ('root','admin','token')`

Indexes:

- index on `(project_id, status, updated_at)` for annotations.
- index on `(project_id, target_type, target_id)` for annotations.
- index on `(annotation_id, revision)` for revisions.

Lifecycle:

- Annotation hard removal deletes both `annotations` and `annotation_revisions` rows and records the deletion in `audit_events`.

### `path_registry`

Columns:

- `path_registry_id TEXT PRIMARY KEY`
- `path_hash TEXT NOT NULL`
- `path TEXT NOT NULL`
- `context_type TEXT NOT NULL`
- `home_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `exp_id TEXT NULL`
- `token_id TEXT NULL`
- `status TEXT NOT NULL`
- `removed_at TEXT NULL`
- `removed_by_credential_id TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Checks:

- `context_type IN ('project','experiment','inspection')`
- experiment and inspection rows have non-null `exp_id` and `token_id`.
- project rows have null `exp_id` and `token_id`.
- `status IN ('active','removed')`
- `removed_at` and `removed_by_credential_id` are null when `status='active'`.
- `removed_at` is non-null when `status='removed'`.

Indexes:

- unique partial index on normalized `path` where `status='active'`.
- unique partial index on `path_hash` where `status='active'`.
- index on `(path_hash, status)`.
- index on `(project_id, exp_id, context_type)`.
- index on `(token_id)`.

Removed path registry rows:

- Removed rows remain for audit and copied-token diagnostics.
- Removed rows do not block reuse of the same path by a later active context.
- A later active context at the same realpath creates a new `path_registry_id`; it never reactivates or overwrites the removed row.

### `locks`

Columns:

- `lock_name TEXT PRIMARY KEY`
- `owner_operation_id TEXT NOT NULL`
- `owner_host TEXT NOT NULL`
- `owner_pid INTEGER NOT NULL`
- `project_id TEXT NULL`
- `exp_id TEXT NULL`
- `acquired_at TEXT NOT NULL`
- `heartbeat_at TEXT NOT NULL`
- `expires_at TEXT NOT NULL`

Indexes:

- index on `(project_id, exp_id)`.
- index on `(expires_at)`.

Expired lock rule:

- Commands attempting to acquire a lock first delete or replace expired locks whose `expires_at` is earlier than the current UTC time.
- `project locks clear-stale` remains available for diagnostics and manual cleanup.

### `runtime_capabilities`

Columns:

- `capability_key TEXT PRIMARY KEY`
- `fingerprint TEXT NOT NULL`
- `status TEXT NOT NULL`
- `details_json TEXT NOT NULL`
- `checked_at TEXT NOT NULL`

Checks:

- `status IN ('supported','unsupported','error')`
- `details_json` is canonical JSON with `schema_version = 1` and contains only safe diagnostic fields.

Rules:

- Runtime capability rows cache safe probes such as Docker daemon availability, Docker platform support, and Docker CPU/memory limit support.
- Docker host-network support is not probed because Docker host networking is not a supported ALab V1 runner option.
- If a probed runtime fingerprint changes, ALab ignores the cached row and probes again.
- `alab config validate --refresh-capabilities` deletes matching capability rows and reruns probes.

### `catalogs`

Columns:

- `catalog_key TEXT PRIMARY KEY`
- `catalog_type TEXT NOT NULL`
- `origin_url TEXT NOT NULL`
- `pinned_commit TEXT NOT NULL`
- `local_path TEXT NOT NULL`
- `status TEXT NOT NULL`
- `metadata_json TEXT NOT NULL`
- `retrieved_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `removed_at TEXT NULL`

Checks:

- `catalog_key IN ('skydiscover')` in V1.
- `catalog_type IN ('skydiscover')` in V1.
- `status IN ('active','removed')`.
- `removed_at` is null when `status='active'` and non-null when `status='removed'`.
- `metadata_json` is canonical JSON with `schema_version = 1` and contains only safe catalog diagnostics.

Rules:

- Catalog rows are home-level metadata. They do not store hidden evaluator asset contents.
- `catalog skydiscover remove` removes the local catalog and marks catalog metadata removed only after dependency checks pass and an audit event is written.
- Historical run, validation, artifact, log, and annotation observation must not require the local catalog files to remain present.

### `cache_entries`

Columns:

- `cache_id TEXT PRIMARY KEY`
- `cache_kind TEXT NOT NULL`
- `cache_key TEXT NOT NULL`
- `project_id TEXT NULL`
- `path TEXT NULL`
- `docker_tag TEXT NULL`
- `size_bytes INTEGER NULL`
- `status TEXT NOT NULL`
- `metadata_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `last_used_at TEXT NULL`
- `removed_at TEXT NULL`

Checks:

- `cache_kind IN ('docker_image','skydiscover_python_env','trash')`.
- `status IN ('active','removed')`.
- `removed_at` is null when `status='active'` and non-null when `status='removed'`.
- `docker_image` rows store a non-null `docker_tag` and null `path`; `skydiscover_python_env` and `trash` rows store a non-null `path` and null `docker_tag`.
- `metadata_json` is canonical JSON with `schema_version = 1` and contains only safe cache diagnostics.

Indexes:

- unique index on `(cache_kind, cache_key)` where `status='active'`.
- index on `(cache_kind, status, last_used_at)`.
- index on `(project_id, cache_kind, status)`.

Rules:

- Dockerfile runner image cache rows use `cache_kind='docker_image'` and store the ALab-owned Docker tag in `docker_tag`.
- SkyDiscover Python evaluator environment rows use `cache_kind='skydiscover_python_env'` and store the environment path under `path`.
- Trash rows are optional cleanup metadata for failed or deferred filesystem deletion; authoritative deletion history remains in `audit_events`.

## 4. JSON Field Contracts

All JSON fields below are canonical JSON objects with integer `schema_version = 1`; boolean `true` is not accepted as a schema version. Unknown top-level keys fail validation unless the contract names an `extensions` object. Renderers may expose only fields marked safe by the owning service result; public and token-scoped renderers must never read `exact`, raw path, hidden, secret, or verifier fields directly from storage.

- `credentials.metadata_json`: keys are `schema_version`, `role` for admin credentials, `token_mode` for token credentials, `created_for_path_hash` for token credentials, and optional `display_label`. It never stores raw secrets or verifier hashes. Credential rows are retained after project or experiment hard remove, so project and experiment ids in this table are denormalized identifiers for audit and diagnostics.
- `audit_events.deleted_ids_json`: keys are `schema_version`, `counts` object, and `ids` object. Object-type keys map to sorted id arrays and deletion counts. It never stores raw secrets, verifier hashes, hidden asset contents, raw hidden logs, or full hidden paths.
- `audit_events.metadata_json`: keys are `schema_version` plus safe audit diagnostics for lifecycle/status transitions, credential ids and types, source refs, context repair, cache/backup pruning, lock clearing, filesystem/trash summaries, optional `blockers`, optional `trash` object or array, optional `filesystem`, optional `config`, optional `credential`, and optional `safe_summary`. Trash paths are relative to ALab home or sanitized same-parent trash labels. It never stores raw secrets, verifier hashes, hidden asset contents, raw hidden logs, or full hidden paths.
- `sources.origin_metadata_json`: keys are `schema_version`, `tree_hash_algorithm`, `primary_origin`, and `origins`. Each origin has `origin_id`, `origin_type`, `safe_summary`, `exact`, `warnings`, and `created_at`. `exact` stores origin-type-specific structured values and must not contain raw credentials, tokens, secret values, hidden asset contents, or raw hidden logs. Token and public output render only `safe_summary` and warning codes.
- `project_config_versions.canonical_config_json`: keys are `schema_version`, `project`, `source`, `runner`, `reward`, `artifacts`, `logs`, `git`, `env`, `secret_env`, `public_source_import`, `mutable`, and `visibility`. Stored `secret_env` entries are `{secret_value_id, fingerprint}` marker objects and never raw secret values.
- `experiments.metadata_json`: keys are `schema_version`, `name`, `name_slug`, `goal`, `creation_origin`, `requested_path`, `source_selector`, and `display`. `creation_origin` records `kind = source|inline_source|from_exp`, resolved ids, the inline source ref when applicable, and resolved commit when inheriting from another experiment. `display` contains safe summaries only.
- `experiments.policy_json`: keys are `schema_version`, `mutable`, optional `mutable_override`, and `visibility_upper_bound`. `mutable` and `mutable_override` store normalized `include` and `exclude` gitwildmatch pattern arrays; `include` must contain at least one non-empty single-line pattern, and `exclude` entries must also be non-empty single-line patterns. `visibility_upper_bound` stores `scope = none|same_project|explicit` and sorted `experiment_ids`; ids are present only for `explicit`, and every entry is a complete experiment id.
- `experiment_submissions.refs_json`: keys are `schema_version` and `refs`. `refs` is an ordered non-empty array containing either the single literal `none` or deduplicated complete experiment ids.
- `runs.record_json` and `project_validations.record_json`: keys are `schema_version`, `config_hash`, `runner`, `reward`, `metrics`, `warnings`, `failure`, `artifacts`, `logs`, `timeout`, `adapter_feedback`, optional `interrupted`, and optional `mutable_scope`. `metrics` is a string-to-finite-number map. `runner` and `adapter_feedback` contain safe summaries only unless the command is root/admin-only. `mutable_scope` stores sanitized `SCOPE_VIOLATION` diagnostics only and uses integer `schema_version = 1` when present.
- `annotations.visibility_json`: keys are `schema_version`, `scope = project|private`, optional `creator_exp_id`, and `constraints`. Private annotations require `creator_exp_id`. Project-visible annotations never expand visibility beyond the target record's visibility.
- `annotations.target_json`: keys are `schema_version`, `target_type`, `target_id`, optional `exp_id`, optional `commit`, optional `repo_path`, and optional `line_range`. Object targets use complete matching object ids in `target_id`, and object target JSON includes the resolved `exp_id`; experiment targets require `target_id == exp_id`. Validation-owned artifact rows do not carry an `exp_id` and cannot be represented as annotation object targets. Path and line target ids are `exp_id:commit:repo_path`. `repo_path` is a normalized forward-slash repo-relative path with no absolute, Windows-absolute, empty, `.`, `..`, backslash, NUL, or newline components. `line_range` stores positive integer 1-based inclusive `start` and `end`, with `end >= start`.
- `runtime_capabilities.details_json`: keys are `schema_version`, `capability`, `safe_summary`, `probed_values`, and optional `error_code`; `capability` is a non-empty string, `probed_values` is an object, and it stores no environment maps.
- `catalogs.metadata_json`: keys are `schema_version`, `safe_summary`, `task_refs`, `evaluator_refs`, and optional `warnings`; task/evaluator refs and warnings are string arrays, and it stores no hidden evaluator contents.
- `cache_entries.metadata_json`: keys are `schema_version`, `safe_summary`, `inputs_hash`, and optional `warnings`; `inputs_hash` is a non-empty string, warnings are a string array, and it stores no raw secrets or hidden asset contents.

`sources.origin_metadata_json` shape:

```json
{
  "schema_version": 1,
  "tree_hash_algorithm": "alab-tree-sha256-v1",
  "primary_origin": {
    "origin_id": "origin-...",
    "origin_type": "local|git|empty|harbor|skydiscover",
    "safe_summary": "string",
    "exact": {},
    "warnings": [],
    "created_at": "2026-05-14T00:00:00Z"
  },
  "origins": [
    {
      "origin_id": "origin-...",
      "origin_type": "local|git|empty|harbor|skydiscover",
      "safe_summary": "string",
      "exact": {},
      "warnings": [],
      "created_at": "2026-05-14T00:00:00Z"
    }
  ]
}
```

Rules:

- `origins` is append-only for active source dedupe and ordered by first observation time, then `origin_id`.
- `primary_origin` is the origin entry that created the source row and never changes.
- `origins` includes `primary_origin` as its first entry, followed by later dedupe observations.
- `exact` stores origin-type-specific structured values and must not contain raw credentials, tokens, secret values, hidden asset contents, or raw hidden logs.
- Public and token-scoped renderers use `safe_summary` and warning codes only.

## 5. Credential Model

Credential prefixes:

- Root key: `alab_root_v1_`
- Project admin key: `alab_admin_v1_`
- Experiment or inspection token: `alab_token_v1_`

Raw credential format:

```text
alab_root_v1_<credential_id>_<secret>
alab_admin_v1_<credential_id>_<secret>
alab_token_v1_<credential_id>_<secret>
```

Rules:

- `<credential_id>` is the public credential row id and is included only to locate the verifier row efficiently.
- Authorization never derives from the id prefix or embedded credential id. The credential type, project scope, experiment scope, token mode, path hash, active status, and salted HMAC verifier must all match.
- Malformed raw credentials, unknown embedded credential ids, type-prefix/type-row mismatches, revoked rows, wrong project scope, wrong experiment scope, and verifier mismatches fail authentication without revealing which part failed.

Storage rules:

- Raw root/admin keys and tokens are generated high-entropy secrets.
- Raw root/admin keys are displayed only once at creation/regeneration.
- Experiment tokens are written only to `.alab/token`.
- SQLite stores credential id, type, project id, exp id, token mode, status, salt, verifier hash, created time, revoked time, and metadata.
- Verifier hashes use a per-credential random 32-byte salt and `HMAC-SHA256(salt, secret)`, verified with constant-time comparison.
- V1 does not use a slow password KDF because generated secrets are high entropy.
- Revocation blocks future CLI access but does not delete data, remove exported files, rewrite commits, or remove copied worktrees.

`.alab/token` rules:

- File content is exactly one raw token line plus one trailing newline.
- Token files should be written with `0600` permissions where POSIX permissions exist.
- Broader permissions produce `TOKEN_FILE_PERMISSIONS`.
- `.alab/token` must be ignored by Git. ALab ensures this by writing worktree-local Git exclude rules for `.alab/` when creating or restoring experiment worktrees and inspection checkouts; token regeneration refreshes that rule for the registered path. ALab staging logic also always excludes `.alab/**`.
- Token regeneration writes the replacement token to the registered path with private permissions and never prints the raw token.

Root lifecycle:

- V1 supports exactly one active root key at a time.
- `auth root regenerate` requires the current active root key.
- Lost root keys are unrecoverable in V1.

Admin key lifecycle:

- `admin` is the only V1 project role.
- Root creates and revokes admin keys.
- Project admin keys cannot create or revoke admin keys.

Token modes:

- `worktree`: submit-capable token stored in an experiment worktree.
- `inspection`: read-only token stored in an inspection checkout.

## 6. Secret Values

`secret_env` handling:

- Values are stored locally in plaintext in `secret_values` but never rendered in normal output, config export, logs, errors, run records, validation records, summaries, or annotations.
- Raw secret values supplied through stdin or files must be non-empty single-line UTF-8 strings with no NUL bytes. ALab strips at most one trailing newline before validation; any remaining newline fails config validation.
- Project config versions store secret value ids and HMAC fingerprints, not raw secret values.
- HMAC fingerprints use the project's non-exported `projects.secret_fingerprint_key` and bind the environment variable name to the value. The HMAC input is the UTF-8 environment name, one NUL byte, then the UTF-8 secret value.
- Experiments resolve `secret_env` through the config version bound at creation.
- Old experiments keep using their original secret values after later secret unset/set commands.
- V1 does not automatically garbage-collect unreferenced secret values.

Redaction:

- Before storing stdout/stderr, ALab redacts exact byte matches of every active `secret_env` value for the experiment's bound config version.
- Each active secret string is encoded as UTF-8 and exact byte matches are replaced with `[REDACTED]`.
- Artifact bytes are stored and exported exactly as captured; V1 does not redact artifact contents.
- If active secrets and artifact globs coexist, run and validation render a warning that artifact bytes are not redacted.

Config export/import:

```toml
[secret_env]
TOKEN = { retain = true, fingerprint = "hmac-sha256:..." }
```

- Export writes retain markers, never raw secrets.
- Import accepts retain markers only for the same project, the same `secret_env` name, and a still-matching stored secret fingerprint. Dry-run imports apply the same retain-marker existence and fingerprint checks.
- User config imports must use `{ retain = true, fingerprint = "hmac-sha256:..." }` retain markers; stored `{ secret_value_id, fingerprint }` markers are internal persisted config data and are not accepted from config files.
- String values in `[secret_env]` create new secret values.

## 7. Global Config

Global config path:

```text
~/.ALab/config.toml
```

Valid V1 schema:

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
- Rich is available only through `--output rich`.
- Time values are integer milliseconds.
- `storage.busy_timeout_ms` configures SQLite `PRAGMA busy_timeout` for ALab database connections.
- Persisted global config accepts only `schema_version`, `[output]`, `[storage]`, and `[locks]` at the top level, and only documented fields inside those tables. Unknown keys or non-table section values fail with `CONFIG_INVALID`.
- Invalid global config stops normal command execution with `CONFIG_INVALID` after home resolution and migration.
- When global config is invalid, only `auth init` and `config show|set|reset|validate` may run so users can diagnose or repair the file.
- `config set` and `config reset` may repair known fields in a partially valid config while preserving other valid configured values. If the TOML file cannot be parsed, only `config reset --all` may rewrite it.
- `config validate --refresh-capabilities` refreshes cached runtime capability probes such as Docker daemon availability, Docker platform support, and Docker CPU/memory limit support.

Global config commands:

```text
alab config show
alab config set <field> <toml-literal>
alab config reset <field>|--all
alab config validate [--refresh-capabilities]
```

## 8. Project Config Persistence

Project definitions are imported/exported as TOML but stored as canonical JSON in `project_config_versions`.

Rules:

- Unknown sections fail.
- Unknown fields fail unless explicitly future-reserved.
- Type mismatches fail.
- Invalid enum values fail.
- Illegal runner/reward/source combinations fail.
- Schema-invalid changes are not written.
- Config edits are based on the latest attempted config.
- Invalid runtime config cannot be made valid by metadata-only edits.
- Runtime-affecting valid changes write `latest_attempted_config_version` and run baseline unless skipped.
- Passing baseline advances `active_valid_config_version`.
- Failure keeps the previous active version and marks the project invalid.
- Non-runtime-affecting valid changes create an `inherited` config version and immediately become active only when the current runtime config is valid. In this case `active_valid_config_version` points at the inherited version, `active_validation_id` points at the validation that proves its unchanged runtime configuration, and `project_config_versions.inherited_from_validation_id` stores the same validation id.
- When the latest attempted runtime config is invalid, metadata-only changes are still based on that latest attempted config and may be written, but they do not advance `active_valid_config_version` or make the project valid.
- `public_source_import.*` is policy configuration and does not require baseline validation.

Project init staging and promotion:

- `project init` allocates project, source, config, validation, and credential ids before filesystem promotion, but it does not write visible project rows until staging has succeeded.
- Staging creates the canonical repository and effective default source snapshot under an ALab-owned temporary operation directory.
- The effective default source may come from the init source selector, an adapter-derived source, or an explicit source accepted by adapter rules. The staged source produces one canonical `alab/source/<source_id>` ref and one canonical tree hash.
- If the input config omits `source.default_source_ref`, ALab injects the staged canonical source ref into the stored canonical config.
- If the input config includes `source.default_source_ref`, ALab treats it as an expected canonical ref. If it differs from the staged canonical source ref, init fails with `CONFIG_INVALID`, does not write project/source/config/credential rows, and removes the staging directory best-effort.
- When staging and full config validation pass, the canonical repository and artifact directories must already exist at their final ALab-owned paths, but no visible project rows have been committed yet. ALab then writes project, source, config version, path registry, and admin credential verifier rows in one short SQLite write transaction.
- The raw project admin key is rendered exactly once only after the DB transaction succeeds. If baseline validation later fails, the retained project becomes `invalid` but the already displayed admin key remains valid.
- If staging or final-path preparation fails before the DB transaction, ALab records `STORAGE_ERROR`, removes staged paths best-effort, writes no project/source/config/credential rows, and must not print the raw admin key.
- If the DB transaction fails after filesystem preparation, ALab records `STORAGE_ERROR`, removes the prepared final paths best-effort, and must not print the raw admin key.

Export:

```text
alab project config export --out <path> [--overwrite] [--project <project_id>] [--version latest-attempted|active-valid|<n>]
```

- Default fails if the target exists.
- `--overwrite` replaces the target.
- Export writes complete TOML with secret retain markers.
- Export defaults to `--version latest-attempted`. `active-valid` fails with `PROJECT_INVALID` when no active valid config exists.

## 9. Context Markers

Marker path:

```text
.alab/context.json
```

Markers are JSON objects with `marker_version = 1`. Unknown top-level keys fail closed. Common keys are `home_id`, `context_type`, `project_id`, `exp_id`, `token_id`, `created_at`, and optional `repaired_at`.

Project marker:

```json
{
  "marker_version": 1,
  "home_id": "home-example",
  "context_type": "project",
  "project_id": "proj-example-a1b2",
  "exp_id": null,
  "token_id": null,
  "canonical_repo_path_hash": "sha256:...",
  "created_at": "2026-05-14T00:00:00Z"
}
```

Project markers additionally require `canonical_repo_path_hash` and must keep `exp_id` and `token_id` null.

Experiment marker uses `context_type = "experiment"`, non-null `exp_id`, and the registered worktree token id. It must not include `canonical_repo_path_hash` or `inspection_commit`.

Inspection marker uses `context_type = "inspection"`, non-null `exp_id`, the inspection token id, and a pinned `inspection_commit`.

Detection sources:

1. Central path registry in SQLite.
2. Local `.alab/context.json` marker in the current directory or an ancestor.

Path identity:

- ALab stores and compares registered paths by resolved absolute realpath.
- Path hashes are hashes of resolved realpaths, not raw user-provided strings.
- On case-insensitive filesystems, path hash input applies the platform's normal case-folding behavior after realpath resolution. On case-sensitive filesystems, case is preserved.
- Symlink aliases are not separate valid registered paths.
- Moving a registered directory requires `alab context repair --path <dir>` or a fresh checkout/create workflow.

Active context nesting:

- Active project, experiment, and inspection contexts generally must not nest inside one another.
- The only allowed nesting is an experiment or inspection context whose nearest active ancestor is the marker-only project control context for the same `project_id`.
- Cross-project nesting is always rejected.
- Experiment and inspection contexts must never contain another active project, experiment, or inspection context.
- A path that would be valid only through the same-project project-control exception must still pass normal realpath registration, empty-directory, and Git worktree checks.

Detection rules:

- If DB registry and marker agree, use that context.
- If a marker exists but DB registry has no matching path, fail with `CONTEXT_CONFLICT`.
- If DB registry maps the path but the marker is missing, fail with `CONTEXT_CONFLICT`.
- If nested markers are found, use the nearest marker only if it matches DB registry; otherwise fail closed.
- A command with explicit `--project` fails with `CONTEXT_CONFLICT` when the current directory is inside a different active ALab project, experiment, or inspection context.
- Outside any context, only global commands and commands with explicit target options may run.
- ALab never auto-repairs marker/registry disagreement during normal command execution. Repair requires explicit `alab context repair --path <dir>` and the credential or self-token checks below.

Capability lookup rules:

- Context detection produces the context input for the CLI capability resolver defined in [spec_cli.md](spec_cli.md).
- Capability lookup is read-only. It may read registry, marker, credential, project status, public project policy, and token mode data needed to decide whether a command is available or locked, but it must not write audit events, repair context state, mutate credentials, read user body/value files, run Git, or execute runners.
- A marker or registry conflict fails closed before capability help or command preflight can render a project or experiment command surface. `alab help --all --explain` may render the safe conflict summary and repair next action, but it must not infer hidden project data from a conflicted marker.
- Explicit root/admin keys may unlock matching project or root command surfaces only after normal credential verification. Ambient `ALAB_KEY` is not a capability lookup input and must not broaden the help surface or token/public command surface.
- The same capability decision must be used for dynamic help and for command preflight. If a direct command invocation is locked by this decision, it fails with `COMMAND_UNAVAILABLE` before command-specific side effects.

`alab context show`:

- Shows marker and registry status for the current or requested path.
- Without credentials it may show marker fields and whether a matching registry row exists.
- Full path registry details require root/admin or the matching valid token.

`alab context repair --path <dir>`:

- Reads `.alab/context.json` from the target path.
- Verifies matching `home_id`.
- Repairs central path registry to the target resolved realpath.
- Root or project admin keys may repair project, experiment, and inspection paths in their scope.
- A valid worktree or inspection token may self-repair only when the old registered realpath no longer exists, marker `token_id` matches the token credential, the raw token verifies, the Git repository is on the registered ALab branch or pinned inspection commit, and the target realpath is not already registered.
- If the old path still exists, token self-repair fails with `CONTEXT_CONFLICT`.
- Successful repair updates registry and marker metadata but never prints or regenerates a raw token.
- Successful repair writes audit metadata with context type, repair mode, path registry id, previous path hash, repaired path hash, whether a registry row was created, and repaired timestamp. It never stores the raw path or raw token.

## 10. Migration And Backup

Migration policy:

- Startup checks schema version before command execution.
- Only forward migrations are supported.
- Migration runs automatically after home resolution and before normal storage access.
- Migration holds an ALAB_HOME-level file lock before opening write-capable migration storage. This lock is separate from the project and experiment `locks` table because the table may not yet exist or may need migration.
- Other commands wait for the lock or fail with `RESOURCE_BUSY` after their configured lock timeout.
- Before applying a migration, ALab uses the SQLite backup API to write a consistent timestamped backup under `~/.ALab/backups/`.
- Directly copying only `alab.db` is not valid because WAL mode may keep committed data in sidecar files.
- Downgrade is unsupported.
- Migration failure stops command execution with `STORAGE_ERROR`.
- Migration files are named `<version>_<slug>.sql` and are applied in ascending integer version order.
- V1 migrations are pure SQL files. Python migration scripts and mixed Python data migrations are not part of the V1 migration contract.
- Data repair that cannot be expressed safely in pure SQL belongs in explicit `repair`, `gc`, or `prune` commands, not in hidden Python migration logic.
- `schema_migrations.checksum` stores `sha256:<hex>` over the exact migration file bytes.
- A changed checksum for an already applied version fails startup with `STORAGE_ERROR`; ALab does not attempt to repair divergent migration history automatically.
- Each migration version runs in one SQLite transaction after the backup succeeds. If a migration transaction fails, ALab rolls it back, leaves the failed version unapplied, and stops command execution.
- If backup creation fails, no migration runs.
- If process interruption leaves the migration lock held, later commands use the home-level file lock's OS semantics; no SQLite `locks` row is required for migration recovery.

Backup naming:

```text
~/.ALab/backups/alab-<schema_from>-to-<schema_to>-<YYYYMMDDTHHMMSSZ>.db
```

Backups are plaintext. They follow the same local security boundary as the main database.

Backup prune:

- `alab backup prune --keep <n>` keeps the newest `n` backups and deletes older backups.
- `alab backup prune --older-than <days>` deletes backups older than the given age.
- `--keep` and `--older-than` conflict.
- Backup prune is root-only and writes an `audit_events` row.
