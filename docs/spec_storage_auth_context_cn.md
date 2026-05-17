# ALab V1 Storage, Auth, And Context Spec（中文）

本文档同步 `spec_storage_auth_context.md`，定义 ALab home state、SQLite storage、credential storage、context detection、config persistence、migration 和 backup 行为。英文版是规范源；本文件用于中文讨论和实现对照。

## 1. Home Identity And Layout

默认 ALab home：

```text
~/.ALab
```

Home resolution priority 为 `--home`、`ALAB_HOME`、`~/.ALab`。

`alab auth init` 生成一个稳定 home id：

```text
home-<random_suffix>
```

规则：

- Suffix 至少包含 128 bits entropy。
- Home id 存入 SQLite，并写入每个 `.alab/context.json`。
- Context detection 和 repair 遇到 marker `home_id` 与 active ALab home 不匹配时 fail closed。
- Home id 不是 secret，不能用于 authorization。

`alab auth init` target path 规则：

- 如果 resolved home path 不存在，ALab 创建它并初始化标准 layout。
- 如果 resolved home path 已存在且是空目录，ALab 可以初始化它。
- 如果 resolved home path 已存在且非空，但不是已初始化的 ALab home，`auth init` 以 `HOME_EXISTS` 失败。
- 如果 resolved home path 已包含 initialized ALab database 或 context state，`auth init` 以 `HOME_EXISTS` 失败。
- `auth init` 不得 merge、overwrite 或 cleanup 非空目录中的 unrelated files。

Canonical filesystem layout：

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

V1 没有 `records/` directory。SQLite 是 structured records 的 authoritative source。Logs 和 artifact bytes 是 plaintext files，由 SQLite 记录引用。

`project-workspaces/` 下的 project workspace directory 只是 project-scoped CLI context 的 marker-only control directory。它们不是 source checkout，不能作为可编辑 experiment worktree 使用。Experiment worktree 是 registered external path。`exp create` 省略 `--path` 时，默认 experiment worktree path 是相对 command cwd 的 `./<project_id>_<exp_id>`。该 cwd 可以是 project control context，但不是必须；任意通过 path registration 和 nesting checks 的 cwd 都有效。

## 2. SQLite Rules

ALab 使用 standard-library SQLite，并在启动时设置：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = <configured milliseconds>;
```

规则：

- Command flow 使用短写事务。
- Source scanning、Git operations、runner execution、Docker build/run、artifact hashing、log capture 等 long-running work 不得持有 SQLite write transaction。
- 不同 experiment 可以并发运行。
- 单个 experiment 的 run/submit path 通过 `locks` table 串行化。
- Typed columns 存储 query-critical fields。
- `*_json` columns 存储完整 structured details 的 canonical JSON。
- Canonical JSON 使用 sorted keys、UTF-8、无无意义 whitespace、稳定 enum strings，并禁止 non-finite numeric values。
- 每个 persisted JSON object 都包含 `schema_version` integer 和文档化 key set。除非该 JSON contract 明确保留 extension object，否则 unknown keys validation fail。
- Datetime 使用 UTC RFC 3339 strings，后缀为 `Z`。
- ID 是 opaque。Authorization 不得从 id prefix 推导。
- CLI object id 参数要求完整 ALab id。Git commit selector 是唯一可以接受 full 或 unambiguous abbreviated SHA 的 identifier。
- Public id 使用 type prefix 加 random high-entropy suffix 以提升可读性，例如 `proj-...`、`src-...`、`exp-...`、`run-...`、`val-...`、`art-...`、`log-...`、`ann-...`。
- 有 human name 时，public id 使用 `<type>-<slug_hint>-<random_suffix>`；否则使用 `<type>-<random_suffix>`。Random suffix 是 22 字符 unpadded base64url string，包含 128 bits entropy。
- Slug hint 使用 NFKC normalization、lowercase ASCII、把连续非 `a-z0-9` 字符折叠为 `-`、移除首尾 `-`，为空时使用 type name。
- Path hash 使用 `sha256:<lowercase_hex>`，输入是经过平台 case normalization 后的 normalized resolved realpath bytes。
- SQLite foreign keys 对 hard remove 后不需要保留 parent 的 authoritative records 使用 restrict-style behavior。Implementation 应在安全的 authoritative parent-child relationships 上使用真实 foreign key；这些 parent 不得在 retained children 仍引用时 hard-remove。Hard remove flow 由 application code 显式检查 dependency、写 audit rows，然后按受控顺序删除 rows。
- 需要保留的 diagnostic 和 audit tables 在必要时存 denormalized object ids，不得要求 foreign keys 指向 hard remove 可能删除的 rows。这包括 `audit_events`、保留的 revoked `credentials`、removed `path_registry` rows，以及仅为 cleanup 或 audit 保留的 cache/catalog metadata。

Plaintext data 可能包含 project names、tasks、config summaries、experiment names、tags、summaries、feedback、annotations、logs、reward values、metrics、artifact metadata and bytes、local paths、source refs、branch names、commit hashes、content hashes 和 `secret_env` values。

## 3. DDL-Level Schema Contract

Implementation 可以添加 internal columns，但以下 tables、constraints、indexes 和 nullability rules 属于 V1 合同。本节是 logical DDL contract，不是 literal migration SQL file；migration SQL 必须至少实现这些 externally observable constraints 和 indexes，且不得削弱文档化行为。

### `homes`

Columns：

- `home_id TEXT PRIMARY KEY`
- `schema_version INTEGER NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Constraints：

- V1 正好一个 active row。
- `home_id` 以 `home-` 开头。

### `schema_migrations`

Columns：

- `version INTEGER PRIMARY KEY`
- `name TEXT NOT NULL`
- `checksum TEXT NOT NULL`
- `applied_at TEXT NOT NULL`

Indexes：

- primary key on `version`。

### `audit_events`

Columns：

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

Checks：

- `actor_type IN ('root','admin','token','system')`
- `action IN ('add','update','archive','unarchive','remove','restore','repair','revoke','regenerate','prune','gc','clear')`
- `object_type IN ('project','source','experiment','run','validation','artifact','log','annotation','credential','secret_value','cache','backup','catalog','lock','worktree','inspection_checkout')`
- `cascade IN (0,1)`
- `reason` 为 null，或是 valid UTF-8 text，编码后长度不超过 65536 bytes。
- `deleted_ids_json` 和 `metadata_json` 是 canonical JSON，并且不得包含 raw secrets、verifier hashes、hidden asset contents 或 raw hidden logs。

Indexes：

- index on `(project_id, created_at)`。
- index on `(project_id, exp_id, created_at)`。
- index on `(object_type, object_id)`。
- index on `(actor_credential_id, created_at)`。

Hard-removed authoritative rows 不保留 row-local `removed_at` field，因为 rows 会被删除。Removal actor、time、cascade flag、deleted ids 和 sanitized metadata 的 authoritative record 是 `audit_events`。

Audit action model：

- `action` 是 generic lifecycle verb。`object_type` 标识被操作对象，例如 `project`、`source`、`experiment`、`run`、`validation`、`artifact`、`log`、`annotation`、`credential`、`secret_value`、`cache`、`backup`、`catalog`、`lock`、`worktree` 或 `inspection_checkout`。
- `catalog_remove`、`worktree_remove`、`worktree_restore`、`checkout_remove` 等历史 special action names 不是 V1 有效 action value。它们由 generic `action` 加具体 `object_type` 表示。

### `credentials`

Columns：

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

Checks：

- `credential_type IN ('root','admin','token')`
- `status IN ('active','revoked')`
- root credential 的 `project_id`、`exp_id`、`token_mode`、`registered_path_hash` 都为 null。
- admin credential 有 non-null `project_id`，并且 `exp_id`、`token_mode`、`registered_path_hash` 为 null。
- token credential 有 non-null `project_id`、non-null `exp_id`，`token_mode IN ('worktree','inspection')`，并且 `registered_path_hash` non-null。

Indexes：

- unique partial index for one active root credential。
- index on `(project_id, credential_type, status)`。
- index on `(project_id, exp_id, token_mode, status)`。
- unique active worktree token per experiment：`(exp_id)` where `credential_type='token' AND token_mode='worktree' AND status='active'`。

### `projects`

Columns：

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

Checks：

- `status IN ('valid','invalid','archived')`
- status 为 `archived` 时，`pre_archive_status IN ('valid','invalid')`；否则为 null。
- `secret_fingerprint_key` 在 project creation 时生成一次，绝不 export，只用于计算 project-scoped HMAC fingerprints，以支持 `secret_env` retain markers 和 secret summaries。

Indexes：

- unique index on `canonical_repo_path`。
- unique index on `control_path`。
- index on `(status, updated_at)`。

### `project_config_versions`

Columns：

- `project_id TEXT NOT NULL`
- `version INTEGER NOT NULL`
- `canonical_config_json TEXT NOT NULL`
- `config_hash TEXT NOT NULL`
- `baseline_required INTEGER NOT NULL`
- `validation_status TEXT NOT NULL`
- `inherited_from_validation_id TEXT NULL`
- `created_at TEXT NOT NULL`
- `created_by_credential_id TEXT NULL`

Primary key：

- `(project_id, version)`

Checks：

- `validation_status IN ('running','passed','failed','error','timeout','skipped','inherited','interrupted')`
- `baseline_required IN (0,1)`
- `validation_status='inherited'` 时必须有 `inherited_from_validation_id`，其他状态下必须为 null。

Indexes：

- index on `(project_id, validation_status)`。
- index on `(project_id, config_hash)`。

Version rules:

- Versions 在每个 project 内单调递增。
- 如果 import/edit 后的 config 与 `latest_attempted_config_version` 的 `config_hash` 完全相同，命令是 no-op，不创建新 version。
- 如果 config 匹配旧 version 但不同于 latest attempted version，ALab 创建新的 monotonic version number，并保存相同 canonical config content。
- V1 中 `config_hash` 不唯一。

Config edit rule：

- Import、set、env、secret changes 基于 `latest_attempted_config_version`。
- Metadata-only change 不能把 invalid runtime config 变成 valid。
- Schema-invalid changes 不写入。

### `secret_values`

Columns：

- `secret_value_id TEXT PRIMARY KEY`
- `project_id TEXT NOT NULL`
- `name TEXT NOT NULL`
- `value TEXT NOT NULL`
- `fingerprint TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `created_by_credential_id TEXT NULL`
- `replaced_at TEXT NULL`

Checks：

- `value` 是 valid UTF-8 text，不包含 NUL，并且 UTF-8 编码后至少 4 bytes。
- `fingerprint` 使用 project-specific HMAC，并以 `hmac-sha256:` 开头。

Indexes：

- index on `(project_id, name, created_at)`。
- index on `(project_id, fingerprint)`。

### `sources`

Columns：

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

Checks：

- `status IN ('active','archived')`
- `source_ref = 'alab/source/' || source_id`

Indexes：

- unique index on `(project_id, name_slug)`。
- unique index on `(project_id, source_ref)`。
- unique partial index on `(project_id, tree_hash)` where `status='active'` for active dedupe lookup。
- index on `(project_id, status)`。

### `experiments`

Columns：

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

Checks：

- `worktree_state IN ('active','removed')`
- `status IN ('open','closed','archived')`
- status 为 `archived` 时，`pre_archive_status IN ('open','closed')`；否则为 null。
- `closed_at` 只有在 status 为 `closed` 或从 closed archived 时 non-null。
- `final_run_removed_at`、`final_run_removed_by`、`final_run_removed_audit_id` 要么全部 null，要么全部 non-null。

Indexes：

- unique index on `(project_id, branch_name)`。
- unique index on `(project_id, json_extract(metadata_json,'$.name_slug'))`。
- index on `(project_id, status, updated_at)`。
- index on `(project_id, source_id)`。
- index on `(project_id, bound_validation_id)`。

### `experiment_submissions`

Columns：

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

Checks：

- `refs_json` 是 canonical JSON，包含 `schema_version = 1` 和 ordered `refs` entries。
- `message` 是 valid UTF-8 text，编码后不超过 300 bytes。
- `summary` 和 `feedback` 是 valid UTF-8 text，各自编码后不超过 65536 bytes。

Indexes：

- unique index on `(exp_id)`。
- index on `(project_id, created_at)`。
- index on `(project_id, final_run_id)`。

Rules：

- 只存 accepted final submissions。
- Failed submit attempts 不创建 submission rows；其 run records 是 authoritative。
- Submission rows 没有独立 archive/remove lifecycle，只随 experiment remove 删除。

### `experiment_tags`

Columns：

- `project_id TEXT NOT NULL`
- `exp_id TEXT NOT NULL`
- `tag_slug TEXT NOT NULL`
- `created_by_type TEXT NOT NULL`
- `created_by_id TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Primary key：

- `(exp_id, tag_slug)`

Checks：

- `created_by_type IN ('root','admin','token')`
- `tag_slug` 是 normalized lowercase ASCII slug，最长 64 bytes。

Indexes：

- index on `(project_id, tag_slug)`。
- index on `(project_id, exp_id)`。

### `runs`

Columns：

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

Checks：

- `status IN ('running','passed','failed','error','timeout','interrupted')`
- `reward_parse_status IN ('not_attempted','parsed','missing','invalid','error')`
- `archive_status IN ('active','archived')`
- `archived_at` 只有在 `archive_status='archived'` 时 non-null。
- `ended_at` 只在 status 为 `running` 时为 null。
- `exit_code` 对 runner start errors 和 interrupted records 可以为 null。

Indexes：

- index on `(project_id, exp_id, started_at)`。
- index on `(project_id, commit_sha)`。
- index on `(project_id, status)`。
- index on `(project_id, archive_status)`。
- index on `(project_id, reward_value)`。

Same commit rule：

- 同一 `commit_sha` 可以有多个 run records。
- 不得有 unique constraint 阻止同一 commit 和 config version 被重复运行。
- Hard removal 只在 run 已 archived 后删除 run rows，并在 `audit_events` 记录删除。

### `project_validations`

Columns：

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

Checks and indexes 在适用处 mirror `runs`。

Additional lifecycle rules：

- 被 `projects.active_validation_id` 引用的 row 不能 archive 或 remove。
- Hard removal 只在 validation 已 archived 后删除 validation rows，并在 `audit_events` 记录删除。

### `artifacts`

Columns：

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

Checks：

- `root IN ('workspace','run')`
- `status IN ('captured','skipped','error')`
- `archive_status IN ('active','archived')`
- exactly one owner is set：`run_id` 或 `validation_id`。
- `blob_path` 只有在 `status='captured'` 时 non-null。
- `capture_error` 在 `status='error'` 时 non-null。
- `archived_at` 只有在 `archive_status='archived'` 时 non-null。

Indexes：

- index on `(project_id, exp_id, run_id)`。
- index on `(project_id, validation_id)`。
- index on `(project_id, content_hash)`。
- index on `(project_id, status)`。
- index on `(project_id, archive_status)`。

### `log_streams`

Columns：

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

Checks：

- `stream IN ('stdout','stderr','hidden_stdout','hidden_stderr')`
- hidden streams 要求 `hidden=1`。
- visible streams 要求 `hidden=0`。
- `archive_status IN ('active','archived')`
- exactly one owner is set：`run_id` 或 `validation_id`。
- `archived_at` 只有在 `archive_status='archived'` 时 non-null。

Indexes：

- index on `(project_id, exp_id, run_id)`。
- index on `(project_id, validation_id)`。
- index on `(project_id, hidden)`。
- index on `(project_id, archive_status)`。

### `annotations` And `annotation_revisions`

`annotations` columns：

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

Checks：

- `target_type IN ('exp','run','artifact','path','lines')`
- `status IN ('active','archived')`
- `resolved_commit` 对 path 和 lines targets non-null。
- `target_json` 是 canonical JSON，包含 `schema_version = 1`，并在适用时保存 resolved experiment id、commit、repo path 和 line range。

`annotation_revisions` columns：

- `annotation_id TEXT NOT NULL`
- `revision INTEGER NOT NULL`
- `body TEXT NOT NULL`
- `author_label TEXT NULL`
- `created_at TEXT NOT NULL`
- `created_by_type TEXT NOT NULL`
- `created_by_id TEXT NOT NULL`

Primary key：

- `(annotation_id, revision)`

Indexes：

- index on `(project_id, status, updated_at)` for annotations。
- index on `(project_id, target_type, target_id)` for annotations。
- index on `(annotation_id, revision)` for revisions。

Lifecycle：

- Annotation hard removal 删除 `annotations` 和 `annotation_revisions` rows，并在 `audit_events` 记录删除。

### `path_registry`

Columns：

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

Checks：

- `context_type IN ('project','experiment','inspection')`
- experiment 和 inspection rows 有 non-null `exp_id` 和 `token_id`。
- project rows 的 `exp_id` 和 `token_id` 为 null。
- `status IN ('active','removed')`
- `status='active'` 时，`removed_at` 和 `removed_by_credential_id` 为 null。
- `status='removed'` 时，`removed_at` non-null。

Indexes：

- unique partial index on normalized `path` where `status='active'`。
- unique partial index on `path_hash` where `status='active'`。
- index on `(path_hash, status)`。
- index on `(project_id, exp_id, context_type)`。
- index on `(token_id)`。

Removed path registry rows：

- Removed rows 保留用于 audit 和 copied-token diagnostics。
- Removed rows 不阻止同一路径之后被新的 active context 复用。
- 同一 realpath 后续出现的 active context 创建新的 `path_registry_id`；它绝不 reactivates 或 overwrite removed row。

### `locks`

Columns：

- `lock_name TEXT PRIMARY KEY`
- `owner_operation_id TEXT NOT NULL`
- `owner_host TEXT NOT NULL`
- `owner_pid INTEGER NOT NULL`
- `project_id TEXT NULL`
- `exp_id TEXT NULL`
- `acquired_at TEXT NOT NULL`
- `heartbeat_at TEXT NOT NULL`
- `expires_at TEXT NOT NULL`

Indexes：

- index on `(project_id, exp_id)`。
- index on `(expires_at)`。

Expired lock rule:

- 命令尝试 acquire lock 前，先删除或替换 `expires_at` 早于当前 UTC time 的 expired locks。
- `project locks clear-stale` 仍保留用于诊断和手动清理。

### `runtime_capabilities`

Columns：

- `capability_key TEXT PRIMARY KEY`
- `fingerprint TEXT NOT NULL`
- `status TEXT NOT NULL`
- `details_json TEXT NOT NULL`
- `checked_at TEXT NOT NULL`

Checks：

- `status IN ('supported','unsupported','error')`
- `details_json` 是 canonical JSON，包含 `schema_version = 1`，且只包含 safe diagnostic fields。

Rules：

- Runtime capability rows 缓存 safe probes，例如 Docker daemon availability、Docker platform support、Docker CPU/memory limit support。
- Docker host-network support 不 probe，因为 Docker host networking 不是 ALab V1 支持的 runner option。
- Probed runtime fingerprint 改变时，ALab 忽略 cached row 并重新 probe。
- `alab config validate --refresh-capabilities` 删除匹配 capability rows 并重新运行 probes。

### `catalogs`

Columns：

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

Checks：

- V1 中 `catalog_key IN ('skydiscover')`。
- V1 中 `catalog_type IN ('skydiscover')`。
- `status IN ('active','removed')`。
- `metadata_json` 是 canonical JSON，包含 `schema_version = 1`，且只包含 safe catalog diagnostics。

Rules：

- Catalog rows 是 home-level metadata，不存 hidden evaluator asset contents。
- `catalog skydiscover remove` 只有 dependency checks 通过并写入 audit event 后，才删除 local catalog 并把 catalog metadata 标记为 removed。
- Historical run、validation、artifact、log 和 annotation observation 不得依赖 local catalog files 仍然存在。

### `cache_entries`

Columns：

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

Checks：

- `cache_kind IN ('docker_image','skydiscover_python_env','trash')`。
- `status IN ('active','removed')`。
- `metadata_json` 是 canonical JSON，包含 `schema_version = 1`，且只包含 safe cache diagnostics。

Indexes：

- unique index on `(cache_kind, cache_key)` where `status='active'`。
- index on `(cache_kind, status, last_used_at)`。
- index on `(project_id, cache_kind, status)`。

Rules：

- Dockerfile runner image cache rows 使用 `cache_kind='docker_image'`，并在 `docker_tag` 中存 ALab-owned Docker tag。
- SkyDiscover Python evaluator environment rows 使用 `cache_kind='skydiscover_python_env'`，并在 `path` 中存 environment path。
- Trash rows 是 failed 或 deferred filesystem deletion 的 optional cleanup metadata；authoritative deletion history 仍在 `audit_events`。

## 4. JSON Field Contracts

以下所有 JSON fields 都是 canonical JSON objects，并包含 `schema_version = 1`。除非 contract 明确命名 `extensions` object，否则 unknown top-level keys validation fail。Renderer 只能暴露标记为 safe 的字段；public/token-scoped renderer 绝不能直接从 storage 读取 `exact`、raw path、hidden、secret 或 verifier fields。

- `credentials.metadata_json`：keys 是 `schema_version`、admin credential 的 `role`、token credential 的 `token_mode`、token credential 的 `created_for_path_hash`，以及 optional `display_label`。它绝不存 raw secrets 或 verifier hashes。Credential rows 在 project 或 experiment hard remove 后仍会保留，所以本表中的 project/experiment ids 是用于 audit 和 diagnostics 的 denormalized identifiers。
- `audit_events.deleted_ids_json`：keys 是 `schema_version`、`counts` object 和 `ids` object。Object-type keys 映射到 sorted id arrays 和 deletion counts。它绝不存 raw secrets、verifier hashes、hidden asset contents、raw hidden logs 或 full hidden paths。
- `audit_events.metadata_json`：keys 是 `schema_version`、optional `blockers`、optional `trash`、optional `filesystem`、optional `config`、optional `credential` 和 optional `safe_summary`。Trash paths 只能是相对 ALab home 的 path，或 sanitized same-parent trash label。它绝不存 raw secrets、verifier hashes、hidden asset contents、raw hidden logs 或 full hidden paths。
- `sources.origin_metadata_json`：keys 是 `schema_version`、`tree_hash_algorithm`、`primary_origin` 和 `origins`。每个 origin entry 的 keys 是 `origin_id`、`origin_type`、`safe_summary`、`exact`、`warnings` 和 `created_at`。`exact` 是 origin-type-specific object，不得包含 raw credential、token、secret value、hidden asset content 或 raw hidden log。Token/public output 只渲染 `safe_summary` 和 warning codes。
- `project_config_versions.canonical_config_json`：keys 是 `schema_version`、`project`、`source`、`runner`、`reward`、`artifacts`、`logs`、`env`、`secret_env`、`public_source_import`、`mutable` 和 `visibility`。`secret_env` entries 存 secret value ids 和 HMAC fingerprints，绝不存 raw secret values。
- `experiments.metadata_json`：keys 是 `schema_version`、`name`、`name_slug`、`goal`、`creation_origin`、`requested_path`、`source_selector` 和 `display`。`creation_origin` 记录 `kind = source|from_exp`、resolved ids，以及适用时的 resolved commit。`display` 只包含 safe summaries。
- `experiments.policy_json`：keys 是 `schema_version`、`mutable` 和 `visibility_upper_bound`。`mutable` 存 normalized `include` 和 `exclude` gitwildmatch pattern arrays。`visibility_upper_bound` 存 `scope = none|same_project|explicit` 和 sorted `experiment_ids`。
- `runs.record_json` 和 `project_validations.record_json`：keys 是 `schema_version`、`config_hash`、`runner`、`reward`、`metrics`、`warnings`、`failure`、`artifacts`、`logs`、`timeout` 和 `adapter_feedback`。`metrics` 是 string-to-finite-number map。`runner` 和 `adapter_feedback` 只包含 safe summaries，除非命令是 root/admin-only。
- `annotations.visibility_json`：keys 是 `schema_version`、`scope = project|private`、optional `creator_exp_id` 和 `constraints`。Private annotations 必须有 `creator_exp_id`。Project-visible annotations 绝不将 visibility 扩大到 target record visibility 之外。
- `annotations.target_json`：keys 是 `schema_version`、`target_type`、`target_id`、optional `exp_id`、optional `commit`、optional `repo_path` 和 optional `line_range`。`line_range` 存 1-based inclusive `start` 和 `end`。
- `runtime_capabilities.details_json`：keys 是 `schema_version`、`capability`、`safe_summary`、`probed_values` 和 optional `error_code`；它不存 environment maps。
- `catalogs.metadata_json`：keys 是 `schema_version`、`safe_summary`、`task_refs`、`evaluator_refs` 和 optional `warnings`；它不存 hidden evaluator contents。
- `cache_entries.metadata_json`：keys 是 `schema_version`、`safe_summary`、`inputs_hash` 和 optional `warnings`；它不存 raw secrets 或 hidden asset contents。

`sources.origin_metadata_json` shape：

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

Rules：

- `origins` 对 active source dedupe 是 append-only，并按 first observation time、再按 `origin_id` 稳定排序。
- `primary_origin` 是创建 source row 的 origin entry，之后不变。
- `origins` 包含 `primary_origin` 作为第一条 entry，后续是 dedupe observation。
- `exact` 存 origin-type-specific structured values，不得包含 raw credential、token、secret value、hidden asset content 或 raw hidden log。
- Public 和 token-scoped renderer 只使用 `safe_summary` 与 warning code。

## 5. Credential Model

Credential prefixes：

- Root key：`alab_root_v1_`
- Project admin key：`alab_admin_v1_`
- Experiment or inspection token：`alab_token_v1_`

Raw credential format：

```text
alab_root_v1_<credential_id>_<secret>
alab_admin_v1_<credential_id>_<secret>
alab_token_v1_<credential_id>_<secret>
```

规则：

- `<credential_id>` 是 public credential row id，只用于高效定位 verifier row。
- Authorization 绝不从 id prefix 或 embedded credential id 推导。Credential type、project scope、experiment scope、token mode、path hash、active status 和 salted HMAC verifier 都必须匹配。
- Malformed raw credential、unknown embedded credential id、type-prefix/type-row mismatch、revoked row、wrong project scope、wrong experiment scope 和 verifier mismatch 都以不泄露具体原因的方式 authentication failed。

Storage rules：

- Raw root/admin keys 和 tokens 都是 generated high-entropy secrets。
- Raw root/admin keys 只在 creation/regeneration 时显示一次。
- Experiment tokens 只写入 `.alab/token`。
- SQLite 存储 credential id、type、project id、exp id、token mode、status、salt、verifier hash、created time、revoked time 和 metadata。
- Verifier hash 使用 per-credential random 32-byte salt 和 `HMAC-SHA256(salt, secret)`，并用 constant-time comparison 验证。
- V1 不使用 slow password KDF，因为 generated secrets 是 high entropy。
- Revocation 会阻止未来 CLI access，但不删除 data、不移除 exported files、不 rewrite commits，也不移除 copied worktrees。

`.alab/token` rules：

- File content 精确为一行 raw token 加一个 trailing newline。
- POSIX permissions 存在时，token file 应以 `0600` permissions 写入。
- 更宽权限产生 `TOKEN_FILE_PERMISSIONS`。
- `.alab/token` 必须被 Git ignore。ALab 在创建或恢复 experiment worktree 和 inspection checkout 时写入 `.alab/` 的 worktree-local Git exclude rule；ALab staging logic 也始终排除 `.alab/**`。
- Token regeneration 将 replacement token 写入 registered path，且绝不打印 raw token。

Root lifecycle：

- V1 同一时间只支持一个 active root key。
- `auth root regenerate` 要求 current active root key。
- Lost root keys 在 V1 不可恢复。

Admin key lifecycle：

- `admin` 是 V1 唯一 project role。
- Root 创建和 revoke admin keys。
- Project admin keys 不能创建或 revoke admin keys。

Token modes：

- `worktree`：submit-capable token，存储在 experiment worktree。
- `inspection`：read-only token，存储在 inspection checkout。

## 6. Secret Values

`secret_env` handling：

- Values 以 plaintext 本地存储在 `secret_values`，但绝不在 normal output、config export、logs、errors、run records、validation records、summaries 或 annotations 中渲染。
- 通过 stdin 或 file 提供的 raw secret values 必须是 non-empty single-line UTF-8 string，且不含 NUL byte。ALab 在 validation 前最多去掉一个尾随换行；任何剩余 newline 都使 config validation 失败。
- Project config versions 存储 secret value ids 和 HMAC fingerprints，不存 raw secret values。
- HMAC fingerprints 使用 project 的 non-exported `projects.secret_fingerprint_key`，并把 environment variable name 绑定到 value。HMAC 输入是 UTF-8 environment name、一个 NUL byte、再加 UTF-8 secret value。
- Experiments 通过 creation 时 bound config version 解析 `secret_env`。
- 后续 secret unset/set 后，old experiments 继续使用它们原来的 secret values。
- V1 不自动 garbage-collect unreferenced secret values。

Redaction：

- 存储 stdout/stderr 前，ALab 会 redact experiment bound config version 下每个 active `secret_env` value 的 exact byte matches。
- 每个 active secret string 按 UTF-8 编码，exact byte matches 替换为 `[REDACTED]`。
- Artifact bytes 按捕获结果原样存储和导出；V1 不 redact artifact contents。
- 如果 active secrets 和 artifact globs 同时存在，run 和 validation render warning，说明 artifact bytes are not redacted。

Config export/import：

```toml
[secret_env]
TOKEN = { retain = true, fingerprint = "hmac-sha256:..." }
```

- Export 写 retain markers，绝不写 raw secrets。
- Import 只在同一 project、同一个 `secret_env` name 且 stored secret fingerprint 仍匹配时接受 retain markers。
- `[secret_env]` 中的 string values 会创建新的 secret values。

## 7. Global Config

Global config path：

```text
~/.ALab/config.toml
```

Valid V1 schema：

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

规则：

- `format = "text"` 是唯一 valid persisted output value。
- Rich 只能通过 `--output rich` 使用。
- Time values 使用 integer milliseconds。
- Invalid global config 在 home resolution 和 migration 后，以 `CONFIG_INVALID` 停止 normal command execution。
- 当 global config invalid 时，只有 `auth init` 和 `config show|set|reset|validate` 可运行，以便用户诊断或修复文件。
- `config set` 和 `config reset` 可修复 partially valid config 中的 known fields，并保留其他 valid configured values。若 TOML 文件无法 parse，只允许 `config reset --all` 重写。
- `config validate --refresh-capabilities` 刷新 cached runtime capability probes，例如 Docker daemon availability、Docker platform support 和 Docker CPU/memory limit support。

Global config commands:

```text
alab config show
alab config set <field> <toml-literal>
alab config reset <field>|--all
alab config validate [--refresh-capabilities]
```

## 8. Project Config Persistence

Project definitions 以 TOML import/export，但在 `project_config_versions` 中存为 canonical JSON。

规则：

- Unknown sections fail。
- Unknown fields fail，除非被明确 future-reserved。
- Type mismatches fail。
- Invalid enum values fail。
- Illegal runner/reward/source combinations fail。
- Schema-invalid changes 不写入。
- Config edits 基于 latest attempted config。
- Invalid runtime config 不能通过 metadata-only edits 变成 valid。
- Runtime-affecting valid changes 写 `latest_attempted_config_version` 并运行 baseline，除非被 skip。
- Passing baseline 推进 `active_valid_config_version`。
- Failure 保留 previous active version，并把 project 标为 invalid。
- Non-runtime-affecting valid changes 创建 `inherited` config version，并且只在 current runtime config valid 时立即 become active。此时 `active_valid_config_version` 指向 inherited version，`active_validation_id` 指向证明其 unchanged runtime configuration 的 validation，`project_config_versions.inherited_from_validation_id` 存同一个 validation id。
- 当 latest attempted runtime config invalid 时，metadata-only changes 仍基于 latest attempted config，并且可以写入，但不推进 `active_valid_config_version`，也不让 project 变 valid。
- `public_source_import.*` 是 policy configuration，不要求 baseline validation。

Project init staging 和 promotion：

- `project init` 在 filesystem promotion 前分配 project、source、config、validation 和 credential ids，但 staging 成功前不写 visible project rows。
- Staging 在 ALab-owned temporary operation directory 中创建 canonical repository 和 effective default source snapshot。
- Effective default source 可以来自 init source selector、adapter-derived source，或 adapter rules 接受的 explicit source。Staged source 生成一个 canonical `alab/source/<source_id>` ref 和一个 canonical tree hash。
- 如果 input config 省略 `source.default_source_ref`，ALab 将 staged canonical source ref 注入 stored canonical config。
- 如果 input config 包含 `source.default_source_ref`，ALab 将其视为 expected canonical ref。若它与 staged canonical source ref 不同，init 以 `CONFIG_INVALID` 失败，不写 project/source/config/credential rows，并 best-effort 删除 staging directory。
- 当 staging 和完整 config validation 通过时，canonical repository 与 artifact directories 必须已位于最终 ALab-owned paths，但 visible project rows 尚未 commit。随后 ALab 在一个短 SQLite write transaction 中写入 project、source、config version、path registry 和 admin credential verifier rows。
- Raw project admin key 只在 DB transaction 成功后渲染一次。如果 baseline validation 后续失败，保留的 project 变为 `invalid`，但已显示的 admin key 仍有效。
- 如果 staging 或 final-path preparation 在 DB transaction 前失败，ALab 记录 `STORAGE_ERROR`，best-effort 删除 staged paths，不写 project/source/config/credential rows，且不得打印 raw admin key。
- 如果 DB transaction 在 filesystem preparation 后失败，ALab 记录 `STORAGE_ERROR`，best-effort 删除已准备的 final paths，且不得打印 raw admin key。

Export：

```text
alab project config export --out <path> [--overwrite] [--project <project_id>] [--version latest-attempted|active-valid|<n>]
```

- 默认目标存在时 fail。
- `--overwrite` 替换目标。
- Export 写完整 TOML，并包含 secret retain markers。
- Export 默认使用 `--version latest-attempted`。没有 active valid config 时，`active-valid` 以 `PROJECT_INVALID` 失败。

## 9. Context Markers

Marker path：

```text
.alab/context.json
```

Project marker：

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

Experiment marker 使用 `context_type = "experiment"`、non-null `exp_id`，以及 registered worktree token id。

Inspection marker 使用 `context_type = "inspection"`、non-null `exp_id`、inspection token id，以及 pinned `inspection_commit`。

Detection sources：

1. Central path registry in SQLite。
2. 当前目录或 ancestor 中的 local `.alab/context.json` marker。

Path identity：

- ALab 按 resolved absolute realpath 存储和比较 registered paths。
- Path hashes 是 resolved realpaths 的 hash，不是 raw user-provided strings 的 hash。
- 在 case-insensitive filesystems 上，path hash input 在 realpath resolution 后使用平台 normal case-folding behavior。在 case-sensitive filesystems 上保留大小写。
- Symlink aliases 不是独立有效 registered paths。
- 移动 registered directory 需要 `alab context repair --path <dir>` 或 fresh checkout/create workflow。

Active context nesting：

- Active project、experiment 和 inspection contexts 通常不得相互嵌套。
- 唯一允许的嵌套是 experiment 或 inspection context 的 nearest active ancestor 是同一 `project_id` 的 marker-only project control context。
- Cross-project nesting 一律拒绝。
- Experiment 和 inspection context 内绝不能包含另一个 active project、experiment 或 inspection context。
- 只有通过 same-project project-control exception 才有效的 path 仍必须通过 normal realpath registration、empty-directory 和 Git worktree checks。

Detection rules：

- 如果 DB registry 和 marker 一致，使用该 context。
- 如果 marker 存在但 DB registry 没有 matching path，以 `CONTEXT_CONFLICT` fail。
- 如果 DB registry 映射了该 path 但 marker 缺失，以 `CONTEXT_CONFLICT` fail。
- 如果发现 nested markers，只在 nearest marker 匹配 DB registry 时使用；否则 fail closed。
- 带 explicit `--project` 的命令，如果当前目录位于另一个 active ALab project、experiment 或 inspection context 内，必须以 `CONTEXT_CONFLICT` 失败。
- 在任何 context 外，只允许 global commands 和带 explicit target options 的 commands 运行。
- ALab 在 normal command execution 中绝不自动 repair marker/registry disagreement。Repair 必须通过 explicit `alab context repair --path <dir>`，并满足下方 credential 或 self-token checks。

`alab context show`：

- 显示 current 或 requested path 的 marker 和 registry status。
- 无 credentials 时，可以显示 marker fields 以及是否存在 matching registry row。
- Full path registry details 要求 root/admin 或 matching valid token。

`alab context repair --path <dir>`：

- 从 target path 读取 `.alab/context.json`。
- 验证 matching `home_id`。
- 将 central path registry 修复为 target resolved realpath。
- Root 或 project admin keys 可以修复其 scope 内的 project、experiment、inspection paths。
- Valid worktree 或 inspection token 只能在 old registered realpath 不再存在、marker `token_id` 匹配 token credential、raw token 验证通过、Git repository 位于 registered ALab branch 或 pinned inspection commit、且 target realpath 未被注册时 self-repair。
- 如果 old path 仍存在，token self-repair 以 `CONTEXT_CONFLICT` fail。
- Successful repair 更新 registry 和 marker metadata，但绝不打印或 regenerate raw token。

## 10. Migration And Backup

Migration policy：

- Startup 在 command execution 前检查 schema version。
- 只支持 forward migrations。
- Migration 在 home resolution 后、normal storage access 前自动运行。
- Migration 在打开 write-capable migration storage 前持有 ALAB_HOME-level file lock。该 lock 独立于 project/experiment `locks` table，因为 table 可能尚不存在或需要 migration。
- 其他 commands 等待 lock，或在 configured lock timeout 后以 `RESOURCE_BUSY` fail。
- 应用 migration 前，ALab 使用 SQLite backup API 在 `~/.ALab/backups/` 下写入 consistent timestamped backup。
- 只直接复制 `alab.db` 不是 valid backup，因为 WAL mode 可能把 committed data 保留在 sidecar files。
- Downgrade 不支持。
- Migration failure 以 `STORAGE_ERROR` 停止 command execution。
- Migration files 命名为 `<version>_<slug>.sql`，并按 ascending integer version order 应用。
- V1 migration 是 pure SQL files。Python migration scripts 和 mixed Python data migrations 不属于 V1 migration contract。
- 无法安全用 pure SQL 表达的数据修复，应放在显式 `repair`、`gc` 或 `prune` 命令中，而不是隐藏在 Python migration logic 中。
- `schema_migrations.checksum` 存储 migration file exact bytes 的 `sha256:<hex>`。
- 已应用 version 的 checksum 如果发生变化，startup 以 `STORAGE_ERROR` 失败；ALab 不自动 repair divergent migration history。
- 每个 migration version 在 backup 成功后用一个 SQLite transaction 执行。如果 migration transaction 失败，ALab rollback，保留该 failed version 为 unapplied，并停止 command execution。
- 如果 backup creation 失败，不运行任何 migration。
- 如果 process interruption 导致 migration lock remain held，后续 commands 使用 home-level file lock 的 OS semantics；migration recovery 不需要 SQLite `locks` row。

Backup naming：

```text
~/.ALab/backups/alab-<schema_from>-to-<schema_to>-<YYYYMMDDTHHMMSSZ>.db
```

Backups 是 plaintext。它们遵循与 main database 相同的 local security boundary。

Backup prune：

- `alab backup prune --keep <n>` 保留最新 `n` 个 backups，并删除更旧 backups。
- `alab backup prune --older-than <days>` 删除超过给定 age 的 backups。
- `--keep` 和 `--older-than` 冲突。
- Backup prune 是 root-only，并写入一条 `audit_events` row。
