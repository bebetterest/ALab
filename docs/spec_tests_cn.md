# ALab V1 Test 规格

本文档是 [spec_tests.md](spec_tests.md) 的中文同步版。英文版是规范性来源。测试应使用 project-local tooling 和隔离的 temporary `ALAB_HOME`。

## 1. Golden CLI Tests

每个命令都需要 golden tests 覆盖：

- Text success output。
- Text result-failure output。
- 适用时的 text system-error output。
- Alias behavior。
- Global options 可在 command/alias 前后出现。
- 每个 registered command 和 alias 都必须有 generated runtime coverage，证明 duplicate global options、missing 或 empty global option values、invalid `--output` values，以及 `--key`/`--key-stdin` conflicts 会在 home creation 或 command matching 前以 `CONFIG_INVALID` 失败。
- 每个 registered command 和 alias 都必须有 generated runtime coverage，证明 trailing global `--home`、`--key` 与 `--output text` 会在 handler option validation 前由 global pre-scan 消费，且 rejected commands 不产生 DB/config/marker/token/tree/worktree side effects。
- Global option pre-scan 在遇到第一个 `--` 后停止，`--` 后的内容完全交给子命令解析。
- 每个 registered non-help command 和 alias 都必须有 generated runtime coverage，证明 standalone `--` 后看起来像 global options 的 tokens 不会被 global pre-scan 消费，不会读取 `--key-stdin`，不会切换选中的 home，并且 rejected command DB/config/marker/token/tree/worktree state 保持不变。
- Command-local options 会在 writes、file exports、runner execution 或 lifecycle audit rows 之前拒绝重复值，除非该 option 明确记录为 repeated。
- 每个 registered command-local singleton option，包括 helper-backed lifecycle aliases，都必须有 generated runtime coverage，证明 duplicate uses 会在 availability fallback、selector lookup、file reads、writes、runner execution 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command/option case 都使用 fresh DB/file/tree/export/worktree snapshots。
- 需要 value 的 global options 会在 home creation 或 command matching 前拒绝缺失 value、空字符串 value，以及下一个 token 看起来像 `--...` option 的情况。
- 需要 value 的 command-local options 会在 file reads、writes、runner execution 或 lifecycle audit rows 之前拒绝缺失 value，以及下一个 token 看起来像 `--...` option 的情况。Structural command-local values 也会在这些 side effects 前拒绝 empty string values；已记录的 direct user-text fields 在 field validators 允许 empty text 时，继续保持 empty string 与 missing/null text 可区分。
- 每个 registered command-local value option 都必须有 generated runtime coverage，证明 absent values 会在 availability fallback、mutually exclusive relationship validation、file reads、writes、runner execution 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command/option case 都使用 fresh DB/file/tree/export/worktree snapshots。
- 每个 registered command-local structural value option 都必须有 generated runtime coverage，证明 empty string values 会在 availability fallback、mutually exclusive relationship validation、file reads、writes、runner execution 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command/option case 都使用 fresh DB/file/tree/export/worktree snapshots；direct user-text empty handling 继续由 multiline/empty text rendering tests 覆盖。
- 每个 registered non-help command 都必须有 generated runtime coverage，证明 unsupported command-local options 会在 handler payload parsing、selector lookup、file reads、writes、runner execution、lifecycle audit rows，或 DB/config/marker/token/tree/worktree mutations 前以 `CONFIG_INVALID` 失败。
- 每个使用共享 typed/structured value parsers 处理 pagination、source limits、retention counts、object id filters、integer filters、numeric filters、boolean filters、sort fields、choice filters 或 time filters 的 registered command，都必须有 generated runtime coverage，证明 malformed values 会以稳定 `CONFIG_INVALID` 失败，且没有 DB/config/marker/token/tree/export/worktree side effects，并且每个 command/option/value case 都使用 fresh snapshots。
- Project config/env/secret mutation conflicts，例如 `--dry-run` 与 `--skip-baseline-test`，必须在读取 config 或 secret payload files、validation writes、DB mutation、marker mutation 或 runner execution 前以 `CONFIG_INVALID` 失败，并且每个 command case 都使用 fresh DB/file/tree snapshots。
- Documented non-remove command conflicts，包括 source selectors、cache/backup selectors、token selectors、submit refs，以及 annotation body/target selectors，必须有 runtime coverage，证明它们输出稳定 errors，且没有 DB/config/marker/token/tree 或 payload-file side effects，并且每个 conflict case 都使用 fresh DB/file/tree snapshots。
- Service handlers 中每个 literal value-option read，包括通过共享 parsing helpers 执行的 reads，都必须登记在 central value-option table 中；该表用于 positional parsing 和 missing-value validation。
- Helper-mediated singleton value-option parsers 必须纳入 static duplicate-guard classification，使它们的 literal option arguments 被视为已 guarded 的 command-local options。
- Guarded service handler 中每个 literal option read，包括 pagination、sorting、source selection、mutable/visibility policy、credential selectors、typed filters 和 time filters 的 helper-mediated reads，都必须出现在该 handler 的 known-option allowlist 中。
- 每个 registered command handler 都必须直接或通过已记录的 lifecycle helper，使用共享 fixed-count 或 optional-selector helper 校验 positional arguments。
- 每个 registered zero-positional command 都必须有 generated runtime coverage，证明额外 positional argument 会在 DB/config/marker/token changes、file exports、source staging、runner execution 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command 都使用新的 DB/file/tree snapshots。
- 每个 registered single-selector command，包括 helper-backed observe 和 annotation lifecycle aliases，都必须有 generated runtime coverage，证明多余 positional arguments 会在 selector lookup、file exports、token/path mutation 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command 都使用新的 DB/file/tree snapshots。
- 每个 registered required single-selector command 都必须有 generated runtime coverage，证明缺失 selector 会在 DB/config/marker/token changes、file exports、checkout creation、source staging、runner execution 或 lifecycle audit rows 前以稳定 object-specific `*_NOT_FOUND` code 失败，并且每个 command 都使用新的 DB/file/tree snapshots。
- 每个 registered fixed-count positional command 都必须有 generated runtime coverage，证明多余 positional arguments 会在 config writes、project/source initialization、secret file reads、config-version writes、tag mutation 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command 都使用新的 DB/file/tree snapshots。
- 每个 registered fixed-count positional command 也必须有 generated runtime coverage，证明缺失 required positional arguments 会在 config writes、project/source initialization、secret file reads、config-version writes、tag mutation 或 lifecycle audit rows 前以 `CONFIG_INVALID` 失败，并且每个 command 都使用新的 DB/file/tree snapshots。
- Stable field labels 和 field ordering。
- 每个命令和 alias 的 primary `object: <type>` 值，包括 list/search result 的 row object type。
- Text output 使用严格 KV object block：每个 object 以 `object: <type>` 开头，warnings 是独立 `object: warning` blocks，errors 也遵守同一 field grammar。
- Text output 的 list fields 始终使用重复字段行，不使用 comma-separated short-list rules。
- Nullable fields 才渲染 literal `none`；用户输入文本必须用 multiline block 表达，空字符串和字面 `none` 与 null 可区分。
- `--output rich` 使用同一 result data，且不会变成 persisted config。
- 所有 object selector 要求完整 ALab object id；只有 Git commit SHA selector 可接受无歧义 abbreviation。
- 所有 time filter 要求带 `Z` 或 numeric offset 的 RFC3339 timestamp。
- 每个 documented command family 都覆盖 command error matrix。
- Stable error code 到 numeric exit code 的固定映射被 golden 覆盖：所有 `*_NOT_FOUND` exit `2`，`PROJECT_INVALID` exit `4`，saved runner/validation error result exit `1`，只有无法保存 intended record 的 system/internal failure exit `5`。
- 覆盖 run、validation、artifact、log、annotation、credential、audit、catalog 和 cache selector 的对象专用 not-found codes。
- `--key` 与 `--key-stdin` mutual exclusion。
- `--key-stdin`、secret `--value-stdin` 和 secret `--value-file` 使用严格 single-line 读取：最多去掉一个 final newline；empty、NUL 或剩余 newline 都失败。
- 空的 ambient `ALAB_KEY` 与未设置 key 等价，不能把 missing-credential failures 变成 `AUTH_DENIED`。
- `ALAB_DEBUG=1` 对 internal errors 打印 stack trace，但不打印 locals/env/secrets/hidden contents。
- README 和 README_cn 中的 opt-in pytest marker commands 必须与 `pyproject.toml` pytest marker declarations 以及 `tests/` 下的实际 marker use 同步。
- Repository root 和 `docs/` 中的每个 Markdown file 都必须保持同步的中文 `*_cn.md` pair，并且这些位置的每个 `*_cn.md` file 都必须有英文 source file。
- README 和 README_cn 的 repository structure trees 必须保持同步，并且每个列出的 path 都必须存在。
- `.gitignore` 必须保持 local agent notes（`AGENTS*.md`、`CORE*.md`）和真实 environment files（`.env`、`.env.*`）被忽略，同时保持 `.env.example` 可被跟踪。
- `.env.example` 必须存在，并覆盖英文和中文 README setup sections 中记录的环境变量赋值，以及 local 和 opt-in validation workflows 使用的核心 ALab/uv/debug knobs。
- 无 command `alab`、`alab help`、`alab --help` 和 nested command help requests 的 context-aware capability help。
- Global、project、experiment 和 inspection context 下的 dynamic help output。
- Invalid global config 会以 `CONFIG_INVALID` 阻断 normal command 和 help execution，同时 `auth init` 与 `config show|set|reset|validate` 仍可用于 diagnosis 或 repair。
- 对 non-repair commands，invalid global config 的优先级高于 explicit credential lookup，因此坏的 `--key` 不能掩盖损坏的 `config.toml`。
- Global config TOML 无法 parse 时，`config set` 和 field-level `config reset` 不能重写文件；只有 `config reset --all` 可以恢复 default config。
- 默认 help 隐藏 locked commands，`alab help --all --explain` 渲染安全 `help_command` rows，其中包含 locked reason、unlock hint、context type、credential source 和 capability source。
- 显式 `--key` 和 `--key-stdin` 解锁 project-admin 或 root surface；ambient `ALAB_KEY` 不影响 help output，也不扩展 token/public command surface。
- Explicit root/admin credential surfaces 必须有 generated runtime coverage，证明 credential surface 外的 registered commands，包括 experiment worktree context 外的 token-only commands，以及 admin key 下的 root-only commands，都会在 handler option parsing、file reads、file/output writes、DB mutation、marker/token mutation、Git operations、runner execution 或 filesystem staging 前以 `COMMAND_UNAVAILABLE` 失败，并且每个 command/payload variant 都使用 fresh DB/file/tree snapshots。
- Root-only long-running dashboard coverage 必须证明 no-key、admin、token 和 public contexts 不能进入 server；invalid port/refresh values 会在 bind 前失败；tests 中 `--no-open` 不打开 browser；startup output 在 serving 前 flush；clean shutdown exit `0`。
- 通过 `--key` 和 `--key-stdin` 传入 invalid explicit credentials 时，必须有 generated registered-command coverage，证明 `AUTH_DENIED` 会在 handler option parsing、unsupported-option validation、config/body/value/summary/feedback file reads、output parent creation、DB mutation、config/marker/token mutation 或 project/source/tmp tree changes 前发生，并且每个 command variant 都使用新的 snapshot。
- 直接调用当前 capability surface 外的 command 时，以 `COMMAND_UNAVAILABLE` exit `4` 失败，并且发生在读取 body/value files、写 SQLite row、创建 audit event、运行 Git 或执行 runner 之前。
- Public project context 必须有 generated runtime coverage，证明每个不属于 public project surface 的 registered command 都会在 handler option parsing、file reads、file/output writes、DB mutation、marker/token mutation、Git operations、runner execution 或 filesystem staging 前以 `COMMAND_UNAVAILABLE` 失败；每个 unsupported option、missing file、config-file 和 output-path payload 都必须使用新的 SQLite/file/tree snapshot。
- Experiment-token context 必须有 generated runtime coverage，证明每个不属于 worktree-token surface 的 registered command 都会在 handler option parsing、file reads、file/output writes、DB mutation、marker/token mutation、Git operations、runner execution 或 filesystem staging 前以 `COMMAND_UNAVAILABLE` 失败；每个 payload 都必须使用新的 SQLite/file/tree/worktree snapshot。
- Inspection-token context 必须有 generated runtime coverage，证明每个不属于 inspection surface 的 registered command 都会在 handler option parsing、file reads、file/output writes、DB mutation、marker/token mutation、Git operations、runner execution 或 filesystem staging 前以 `COMMAND_UNAVAILABLE` 失败；每个 payload 都必须使用新的 SQLite/file/tree/checkout snapshot。

覆盖命令：

- `help`、无 command `alab`、`alab --help` 和 nested command help。
- `auth init`、`auth root regenerate`。
- `config show`、`config set`、`config reset`、`config validate`。
- `dashboard`。
- `key create`、`key list`、`key revoke`。
- `context show`、`context repair`。
- `project list/show/archive/unarchive/remove/status/init/config/env/secret/validate/validation/locks`。
- `source import/list/show/archive/unarchive/remove`。
- `catalog skydiscover add/update/show/remove`。
- `cache prune`，包括 `--trash --older-than`、`--trash-all` 和 top-level `--all`。
- `backup prune`。
- `audit list`、`audit show`。
- `project secret gc`。
- `exp create/archive/unarchive/remove/checkout/worktree/token/tag`。
- `run`、`submit`。
- `observe experiments/runs/artifacts/logs/annotations`，包括 runs/artifacts/logs archive、unarchive 和 remove。
- Top-level aliases：`status`、`exp`、`runs`、`artifacts`、`logs`、`annotations`。
- `annotate add/edit/archive/unarchive/remove`。

Lifecycle golden cases：

- 每个实际 hard remove command 都拒绝缺少 `--force`、缺少 `--confirm`、confirm id 错误、target 未 archived 的情况，并且没有 DB/file/tree/trash side effects；每个 command 和 confirmation variant 都必须使用新的 snapshots。
- 每个 hard remove command 都支持 `--dry-run`，输出 blocker 和 deletion count，且不写 audit row、不删除数据；target 未 archived 时输出稳定的 `target_not_archived` blocker 并 exit `0`；dry-run coverage 必须证明每个 command 的 fresh DB/file/tree/trash snapshots 保持不变。
- 每个 `--cascade` command 在存在 active dependent authoritative object 时失败，并输出稳定 blocker list；dependency-blocker coverage 必须逐 command 证明 DB/file/tree/trash 和 source Git refs 保持不变。
- Archive 和 unarchive command 是幂等的；目标已经处于请求状态时成功返回，且不写重复 audit row。
- Error matrix cases 确认重复 archive/unarchive 操作永远不返回 `PROJECT_ARCHIVED`、`EXPERIMENT_ARCHIVED` 或任何 already-archived failure code。
- `HOME_EXISTS` 和 `OUTPUT_EXISTS` 渲染稳定 text errors。
- Public 或 optionally authorized 命令忽略 ambient `ALAB_KEY` 的权限提升效果，只有显式 `--key` 或 `--key-stdin` 才渲染 authorized details。
- Ambient `ALAB_KEY` 只能为已经在当前 context surface 可用的命令满足 authentication；它绝不扩展 default help、public project surface、experiment token surface 或 inspection token surface。
- Public project status coverage 证明 invalid projects 在 no key、ambient `ALAB_KEY`，以及通过 public surface 放行的 explicit non-admin credentials 下都会渲染缩减的 public-invalid field set。
- Global explicit project admin key help 显示可通过显式 project id 运行的 same-project admin commands；不显示 root-only cache、catalog、backup、global audit 或 project creation capabilities。
- Experiment token help 隐藏 project config、project init、source management、experiment remove、worktree maintenance、cache、catalog、backup、audit 和 key-management commands。
- Inspection token help 隐藏 run、submit、tag mutation、annotation mutation、project/source/config management、experiment mutation、worktree maintenance、cache、catalog、backup、audit 和 key-management commands。
- Project no-key help 只在 project policy 允许时显示 public safe status 和 public experiment/source bootstrap。
- Public experiment creation coverage 证明有效但不匹配 target project 的 explicit credential 会在 policy 允许时按 public surface 执行，而 `project.allow_public_exp_create = false` 会隐藏并 preflight-block public `exp create` 且无 side effects。
- Experiment 或 inspection path 中的 explicit admin/root key 会解锁匹配的 same-project capability，但指向不同 active context 的 explicit `--project` 仍以 `CONTEXT_CONFLICT` 失败。
- Token/public caller 选择不可见对象时返回非泄露 `SCOPE_VIOLATION`，reason 为 `not visible or not found`。
- `exp archive` 拒绝已移除的 V1 flags `--remove-worktree` 和 `--force-remove-worktree`。
- Archived artifact/log export 在没有 `--include-archived` 时失败；authorized by-id show 成功。
- Config、artifact 和 log export 在 target exists 且未提供 `--overwrite` 时以 `OUTPUT_EXISTS` 失败。

Dashboard security cases：

- `alab dashboard` 只绑定 `127.0.0.1`，在 URL fragment 生成随机 browser token，并要求每个 `/api/*` request 携带 `X-ALab-Dashboard-Token`。
- Missing 或 wrong API token 返回 `401`；unknown routes 返回 `404`；非 GET/HEAD methods 返回 `405` 且不 mutate state。
- API responses 和 frontend assets 绝不暴露 raw root/admin keys、raw experiment tokens、credential verifier material、salts 或 raw `secret_env` values。
- Root dashboard sessions 可以通过 path-contained file reads 读取 hidden log full text 和 raw artifact/log download bytes。
- Static assets 避免 inline event handlers，并保持 dashboard CSP-compatible。

## 2. Storage 和 Migration Tests

覆盖：

- DDL constraints 和 enum checks。
- Running/error/interrupted run records 所需 nullable fields。
- Project、experiment、run、source、artifact、log、annotation、credential、registry、lock queries 所需 indexes。
- WAL mode setup。
- Migration 前使用 SQLite backup API backup。
- Migration ordering 和 checksum recording。
- Global migration lock behavior。
- Downgrade rejection。
- Canonical JSON ordering 和 hash stability。
- Credential verifier storage 不含 raw root/admin/token secrets。
- Raw root/admin/token wire format 包含 credential id（例如 `alab_admin_v1_<credential_id>_<secret>`），且 verifier lookup 只能把 id 用作定位 hint，授权仍依赖 HMAC、scope 和 status。
- `secret_values` 中本地 plaintext `secret_env` storage，以及使用 non-exported project fingerprint key 生成 project-scoped HMAC fingerprints。
- One active root key partial uniqueness。
- Admin key project scoping。
- Token mode 和 active worktree token uniqueness。
- `home_id` creation 和 context marker matching。
- Path registry realpath hashing。
- Secret value storage、HMAC fingerprints、retain markers、unset behavior、GC candidate calculation。
- Secret HMAC fingerprints 绑定 `secret_env` name 和 value，retain markers 不能换名复用。
- Secret value 拒绝 empty、含 NUL、短于 4 bytes 的值。
- Config edits based on latest attempted config。
- Config edits 跳过 continuous no-op configs，回滚旧内容时创建 monotonic versions，并且不要求 unique config hashes。
- Metadata-only config edits 在 current runtime config valid 时创建 active `inherited` versions，并让 `active_validation_id` 继续指向证明 unchanged runtime config 的 validation。
- Metadata-only config edits 不验证 invalid runtime config。
- Config export 默认 target exists 时失败，带 `--overwrite` 成功。
- `project secret gc` 必须且只能使用 `--dry-run` 或 `--apply` 之一；dry-run 不写 audit row，apply 只删除 unreferenced raw secret values。
- Lifecycle DDL columns 和 checks 覆盖 project/source/experiment `pre_archive_status`、experiment `worktree_state`、run/validation/artifact/log `archive_status`、final run removed metadata、path registry `removed` state 及 removed metadata。
- DDL 覆盖 `experiment_tags`、`experiment_submissions`、`runtime_capabilities`、`catalogs`、`cache_entries`、`projects.secret_fingerprint_key`、`experiments.bound_validation_id`、`annotations.target_json` 和 explicit validation archive columns。
- Retained `audit_events`、revoked `credentials`、removed `path_registry` rows 和 cache/catalog metadata 在 hard removal 后不会因为指向 deleted authoritative rows 的 foreign keys 而损坏。
- Metadata、policy、record、target、visibility、origin、audit 和 submission refs JSON 都有 strict versioned JSON contracts。
- `audit_events` columns、generic action/object_type enum constraints、JSON metadata constraints，以及 hard remove、cache/catalog/backup prune、lock clear、final run deletion 的 event creation。
- Migration 使用 ALAB_HOME-level file lock，并覆盖 configured timeout 后以 `RESOURCE_BUSY` 失败；project 和 experiment operations 使用 SQLite `locks` table。
- Global config defaults、SQLite busy-timeout application、invalid config repair-only behavior、field-level repair、`reset --all`，以及用于 Docker availability/platform/resource probes 的 `validate --refresh-capabilities`。
- Audit list/show authorization 和 sanitized metadata rendering。
- Path registry `status='removed'` rows 不阻止 path reuse，但仍可用于 audit 查询。
- `path_registry_id` 是 primary key；active `path_hash` unique；removed rows 不阻止 path reuse；重用同一路径会创建新的 registry row。
- Explicit `--project` 与当前 active ALab context 不一致时的 context conflict。
- Active context nesting 允许同一 project 的 marker-only project context 下创建 experiment/inspection context，拒绝跨 project nesting，并拒绝 experiment/inspection context 内再嵌套任何 active context。
- DB path registry 与 `.alab/context.json` 不一致时默认 fail closed；只有严格认证后的 explicit `context repair` 可修复。
- Capability lookup 是 read-only，使用与 command execution 相同的 context detection result，并且在 marker/registry disagreement 时 fail closed，不做 auto-repair。
- 同一 argv、context 和 explicit credential 下，capability resolver 对 help rendering 和 command preflight 的 decision 必须一致。
- Case-insensitive filesystem 上 path hashing 应用 platform case normalization。

## 3. Auth、Context 和 Lifecycle Tests

覆盖：

- `auth init` 创建 home，并只显示 generated root key 一次。
- `auth init` 对 missing 或 empty home directory 成功；对已初始化 home 或非空 unrelated directory 以 `HOME_EXISTS` 失败。
- Root key regeneration 替换 root key 并 revoke previous verifier。
- Lost-root unrecoverability。
- Project admin key create/list/revoke root-only behavior。
- Experiment token list metadata 不含 raw token 或 verifier hash。
- Token regeneration 写 registered `.alab/token`，绝不打印 raw token。
- Token file 是一行 raw token，并被 Git ignore。
- Token file permission warnings。
- Context marker parsing。
- `context show` marker/registry output。
- Context conflict detection。
- Root/admin `context repair`。
- Moved experiment/inspection path 的 strict token self-repair。
- Copied token self-repair 在严格条件不满足时 blocked。
- Project archive/unarchive 恢复 pre-archive status。
- Experiment archive/unarchive 恢复 pre-archive status。
- Source archive/unarchive constraints，包括 active default source block。
- Project/source/experiment hard remove 要求 archived state、正确 confirmation 和允许的 cascade dependencies。
- Filesystem hard remove 把 ALab-owned paths 移入 `tmp/trash/<audit_id>/`，立即尝试删除，失败时记录 residual trash path，并支持 `cache prune --trash --older-than` 和 `cache prune --trash-all`。
- Filesystem hard remove 对 cross-device moves 使用 same-parent `.alab-trash-<audit_id>` fallback；如果 trash move 后 audit/DB transaction 失败，会 best-effort restore original path。
- Expired locks 在 lock acquisition 时自动替换；`locks clear-stale` 保留为 diagnostic。
- Lifecycle audit rows 覆盖 archive、unarchive、remove、restore、repair、revoke、regenerate、prune、gc、catalog remove、worktree remove/restore 和 checkout remove。
- Project remove 仅 root 可执行，要求 `--cascade`；project archived 且无 active locks 时作为 whole-tree special case 删除 project DB tree、child records 和 filesystem state，child records 不要求逐个 archived，并保留 revoked credential rows 用于 audit。
- Source remove 在任意 project config version 引用该 source 时始终失败；否则默认在 active experiment 依赖它时失败，只有 dependent experiments 已 archived 时 `--cascade` 才成功；source remove 不使用 whole-tree exception。
- Experiment remove 删除 branch/worktree/inspection contexts；experiment archived 且无 active run/submit 时作为 whole-experiment special case 删除 dependent run/log/artifact/annotation/tag/submission records，并 revoke tokens。
- Run lifecycle 支持 own worktree token、root、admin archive/unarchive；regenerated worktree token 继续允许 archive/unarchive 自己实验的 run/artifact/visible log。
- Run remove 仅 root/admin 可执行，要求 archived run，重新计算 `latest_run_id`，并在删除 `final_run_id` 时保留 closed experiment final metadata。
- Project validation archive/remove 仅 root/admin 可执行，且 active validation proving `active_valid_config_version` 被阻止。
- Worktree remove 可用于 open、closed、archived experiments，支持 `--dry-run`；actual deletion 要求 root/admin 加 `--force --confirm <exp_id>`，记录 dirty discard behavior，通过 trash staging 删除 filesystem，revoke active worktree token，将 path registry row 标记为 `removed`，并设置 `worktree_state='removed'`。
- Run 和 submit 拒绝 `worktree_state` 为 `removed` 的 experiment。
- Worktree restore 要求 `--path`，目标必须 empty 或 nonexistent，checkout branch HEAD，写 `.alab/context.json`，创建新 token，写 `.alab/token`，并设置 `worktree_state='active'`。
- Inspection checkout remove 支持 `--dry-run`；actual deletion 通过 trash staging 删除 inspection worktree，registered path 已缺失时会调和状态，revoke 其 token，将 path registry row 标记为 removed，且没有 restore command。

## 4. Project 和 Source Tests

覆盖：

- Project init from local path、remote Git fixture、empty source、Harbor fixture、SkyDiscover fixture。
- 所有 runner type 的 project init 都要求 `--config`，并拒绝 runner/reward/artifact/log/env runtime flags。
- `project init harbor/skydiscover` 拒绝指向 existing ALab source 的 `--source-ref`，只接受 path/Git/empty 或 adapter-derived source。
- Project init 在 DB commit 前完成 filesystem staging，在一个 transaction 中写入 project/source/config/admin credential rows，并只在 transaction 成功后打印 admin key。
- Project init 只有在提供且只提供一个 init source origin 时才接受缺少 `source.default_source_ref` 的 config，并存储注入后的 canonical source ref。
- Project init 在 input `source.default_source_ref` 与 staged canonical source ref 不匹配时以 `CONFIG_INVALID` 失败。
- Adapter init 对 explicit source 和 adapter-derived source 的 canonical tree hash 相同 case 执行 dedupe；不同 case 以稳定 source conflict 失败。
- Baseline pass 创建 valid project。
- Baseline fail 创建 invalid project，并保留 project/source/config/validation/log/artifact records。
- `--skip-baseline-test` 写 config 并标记 invalid。
- `project validate` 恢复 valid status。
- Invalid project 阻止 new `exp create`。
- Project invalidation 后 existing experiments 继续用 bound valid config version run/submit。
- Experiment creation 存储 `bound_validation_id`。
- Default experiment worktree path 是相对 command cwd 的 `./<project_id>_<exp_id>`；ALab home layout 没有默认 `workspaces/` tree。
- Project control context 位于 `project-workspaces/<project_id>/.alab/context.json`，且只是 marker-only。
- Archived projects、sources、experiments 默认隐藏，并在定义了 include flag 的地方显式 include 后可见。
- Closed experiments unarchive 后仍保持 closed。
- Project init 在写入 project record 时始终创建一个 admin key 并只打印一次，包括 baseline failed 后保留 invalid project 的情况。
- Public safe status rendering。
- Public no-key project context 不能 observe/show/config。
- Public projects 允许 no-key experiment creation from allowed sources and visible experiments。
- Public no-key `--from-exp` 支持通过 current project public policy 与 source experiment stored visibility upper bound 交集可见的 open/closed experiment 的 `final`、`latest`、`best` 和 reachable SHA selector。
- Public no-key `--from-exp` 不能从 current project public policy 列出但被 source experiment stored visibility upper bound 排除的 experiment 继承。
- Public no-key `--from-exp` 拒绝 archived source experiment，除非提供 root/admin。
- Public no-key checkout/observe history 被拒绝。
- Public remote Git import 由 `[public_source_import]` 控制。
- Public remote Git import 在可能使用 local non-interactive Git credential helper 时渲染 `PUBLIC_GIT_CREDENTIAL_HELPER_USED`，并保持 prompts disabled。
- `project config show/export` 默认使用 `--version latest-attempted`，支持 `--version active-valid|<n>`；没有 active valid config 时，`active-valid` 以 `PROJECT_INVALID` 失败。
- `project config import/set --dry-run` 不写 DB rows、不修改文件、不创建 audit rows、不执行 baseline runners。
- Project config/env/secret mutations 不写 lifecycle audit rows；config versions 和 secret rows 是 authoritative records。`project secret gc --apply` 仍然 audited。
- `public_source_import.*` changes 不触发 baseline validation。
- Public source limits 默认等于 source limits，且可配置，无 hard-coded cap。
- `[env]` 和 `[secret_env]` 中的 environment variable names 必须匹配 `^[A-Za-z_][A-Za-z0-9_]*$`。
- `project config set` 替换完整 map/array 字段，不做 deep merge。
- Private project 创建 experiment 需要 root/admin。
- Source import local filesystem snapshot 包含 uncommitted unignored files。
- Source import 排除 untracked sensitive files。
- Local source path 位于 Git worktree 时，tracked files 仍导入；`.alabignore`、Git ignore 和内置 sensitive filters 只过滤 untracked files。
- Tracked sensitive source files 输出 warnings。
- Remote Git imports 使用 `--git-ref`。
- Existing ALab source selection 使用 `--source-ref`。
- Source name omitted 时 auto-derive。
- Empty-after-filter warnings。
- Subdir handling。
- Content hash dedupe 返回 existing source。
- Canonical source tree hash 使用 `alab-tree-sha256-v1`，且独立于 Git object hash format。
- Git submodule/gitlink source entries 以 `SOURCE_INVALID` 失败，并提示先 vendor 或展开 submodule content。
- Source dedupe 追加 stable sanitized `origin_metadata_json.origins` entry，不创建新 source ref。
- Archived sources 不参与 source dedupe。
- Source name slug uniqueness。
- Limit enforcement。

## 5. Run 和 Submit Tests

覆盖：

- Experiment create at default/custom paths。
- Experiment name slug conflict 对所有 caller 都以 `NAME_CONFLICT` 失败，包括 public no-key caller。
- Default experiment path 是 `./<project_id>_<exp_id>`，存在时失败；可从任意通过 path 和 nesting checks 的 command cwd 创建，project control context 允许但不是必需。
- Custom experiment path 拒绝任何 existing entry。
- Experiment mutable/visibility override 可收窄但不可扩展。
- 在同一 project 的 marker-only project control context 内创建默认 worktree/inspection 成功；不同 project 必须显式选择非嵌套 path。
- Experiment mutable override 在 run/submit 时按 project policy 与 stored experiment override 的 intersection 生效。
- Experiment visibility override 在创建时归一化为 project policy 与 requested override 的 intersection，并作为 experiment upper bound 存储。
- Mutable patterns 使用 pathspec GitWildMatchPattern semantics，rename/copy scope validation 要求 source path 和 destination path 都被允许。
- Experiment 和 inspection context 中 `alab status`。
- Run with changes 创建 commit。
- ALab auto commit 前写 `running` run record。
- Run-created commit 使用 `ALab run: <message>` 和 ALab trailers。
- Full-diff scope failure after ALab auto commit 只 rollback 该 auto commit，保留 file changes，并存 rolled-back commit hash 和 explanation。
- Auto-commit rollback 后 file changes 保持 unstaged。
- Full-diff scope failure caused by existing manual commit 记录 run `error`，返回 actionable `SCOPE_VIOLATION` details，并保持 HEAD/worktree 不变。
- Run on manual commit 在 full diff in scope 时 accepted。
- Existing legal manual commit 且 worktree 又有 dirty changes 时，`alab run` 先校验 baseline 到 current HEAD 的 full diff，再自动提交 dirty changes，最后对 resulting target commit 重复 full-diff mutable scope check。
- Run rejects invalid Git states and out-of-scope changes。
- Existing staged changes 被包含。
- Run auto commit 包含所有 mutable-allowed staged、unstaged、deleted、renamed、copied 和 untracked non-ignored changes。
- Empty-change run 不创建 commit 但存 run record。
- Same commit 可以有多个 run records。
- Stale `running` run records 变 `interrupted`。
- Failed run 存 logs、artifacts 和 parsed reward when available。
- Run 和 submit 要求 `experiments.worktree_state = 'active'`。
- `alab submit` 要求 project 未 archived；closed experiment 仍允许 tag/annotation mutation。
- Submit 只接受 summary/feedback text 或 file。
- Submit summary/feedback file 相对 current cwd resolve。
- Submit stdin options rejected。
- Submit refs dedupe preserving first-seen order。
- Submit 只在 passed final run 后存一条 `experiment_submissions` row。
- Summary、feedback 和 annotation bodies 拒绝 exact active secret values。
- Submit reuse 和缺少 reusable passed run 时要求 explicit `--rerun`。
- Submit reuse 只允许 current HEAD 且 experiment bound config version 相同的最近 passed run。
- Failed submit 不设置 final summary、feedback、refs、final commit、final run id。
- Passed submit closes experiment。
- 持久化 user text limits 使用 UTF-8 bytes：run message、submit summary/feedback 和 annotation bodies 覆盖 boundary cases，包括 multi-byte UTF-8 input。

## 6. Runner、Reward、Log 和 Artifact Tests

覆盖：

- Local runner `env_mode` handling。
- `runner.shell` 只支持 local runner 和 Docker runner shell mode，并被 Harbor 和 SkyDiscover runner 拒绝。
- Runner environment 即使在 `env_mode = "full"` 下也剔除 `ALAB_KEY` 等 ALab credential variables。
- `env_mode = "full"` 渲染 stable warning，说明 `secret_env` 之外的 host env secrets 不保证 redacted。
- Temporary runner workspaces 绝不包含 `.alab/token` 或 `.alab/context.json`。
- Fixed internal env injection：`ALAB_PROJECT_ID`、`ALAB_EXP_ID`、`ALAB_RUN_ID`、`ALAB_CONFIG_VERSION`、`ALAB_WORKSPACE`、`ALAB_RUN_DIR`。
- Internal env override user env values。
- SkyDiscover Python evaluator-wrapper execution 会保持 runner environment boundary，包括 host ALab credential stripping、internal env override precedence、user env 和 secret env injection，以及 hidden-output secret redaction。
- Closed runner stdin behavior。
- Local runner timeout terminates process group。
- Runner start、Docker unavailable、adapter 和 dependency-installation errors 在存在 saved run/validation records 时 exit `1`，不是 `5`。
- `runner.working_directory`、reward path 和 artifact path 等依赖 source contents 的字段在 config 阶段只验证类型和 escape；缺失 path 在 baseline/run 中保存失败记录。
- Reward extractors：`exit_code`、`file`、`stdout_regex`、`harbor`、`skydiscover`。
- File reward read limit reuses artifact per-file limit。
- JSON reward metrics top-level only。
- Stdout regex reads redacted/truncated stdout。
- Non-zero exit 和 zero exit 下 reward parse status behavior。
- Artifact root parsing and escape rejection。
- Artifact directory expansion。
- Artifact glob capture 使用 Python glob semantics、escape checks、resolved path dedupe 和 stable sorted output。
- Artifact symlink capture/skip behavior。
- Oversized artifacts skipped without changing run/validation status。
- Artifact capture errors 记录为 artifact statuses 和 `ARTIFACT_CAPTURE_ERROR` warnings，且不改变 run/validation status。
- Exact-byte artifact export。
- Artifact export overwrite behavior。
- Artifact/log archive 和 unarchive visibility defaults。
- Artifact/log remove 仅 root/admin 可执行，要求 archived state，并写 audit events。
- Shared artifact blobs 和 shared log files 保留到没有任何 row 引用它们。
- Archived artifact/log export 要求 `--include-archived`；authorized by-id show 成功。
- Non-zero exit、reward parse error、runner error 和 timeout 后仍 best-effort 采集 logs/artifacts。
- No artifact secret redaction guarantee。
- 配置了 active `secret_env` values 和 artifact globs 时，会 render 并 persist `ARTIFACT_BYTES_NOT_REDACTED` warnings，同时 logs 仍然 redacted，artifact exports 保持 exact bytes。
- Log truncation。
- Byte-based secret redaction before log storage。
- Secret redaction 发生在 log truncation 之前。
- Log byte-file storage metadata。
- Fixed run previews。
- `observe logs list/show/export`。
- Hidden log authorization 需要 root/admin plus `--include-hidden`。
- Hidden log lifecycle 在 archive/unarchive/remove attempts 中保持 hidden permission rules。

## 7. Adapter Tests

Docker：

- Docker unavailable 时 Docker-backed validation 为 `error`，project invalid。
- Docker unavailable 时 Docker tests skip。
- Docker runner validates repo-relative Dockerfile/context paths。
- Docker runner uses `/app` and `/logs/alab`。
- Docker setup/build output 渲染 `DOCKER_SETUP_OUTPUT_CAPTURED`，将 setup bytes 作为 redacted hidden logs 存储，且不把 setup bytes 合并到 user-visible runner stdout/stderr。
- Docker network modes：`default` 和 `none`。
- `runner.network = "host"` 以 `CONFIG_INVALID` 被拒绝。
- Docker runner 支持 whitelisted `build_args`、`target`、`platform`、`user`、`cpus`、`memory_mb`。
- Docker-backed runners 不继承 host environment variables。
- Missing `runner.image` images 会自动 pull；pull failure 在可能时记录为 saved `RUNNER_ERROR` result。
- Dockerfile build context 遵循 `.dockerignore`，Dockerfile image cache keys 包含 Dockerfile content、`.dockerignore` 和 effective filtered build context。
- Unsupported configured Docker CPU or memory limits fail before config write。
- Dockerfile image cache key 只包含 build inputs；run-time fields 不应创建 duplicate cached images。
- Docker runtime capability probes 覆盖 availability、platform 和 resource support，按 runtime fingerprint cache，并可通过 `config validate --refresh-capabilities` 刷新。
- Dockerfile runner 在 `cache_entries` 创建 ALab-owned image cache metadata，`cache prune --docker-images|--all` 可删除。
- Docker runner 拒绝 raw Docker argument passthrough、privileged mode、extra host mounts 或 volumes。
- Unreadable container output records capture errors。

Harbor：

- Single-step Harbor task with shared verifier。
- Single-step Harbor task with separate verifier image。
- Single-step Harbor task with separate verifier `tests/Dockerfile`。
- Default fake-Docker Harbor runner tests 必须覆盖 shared verifier、separate verifier image、separate `tests/Dockerfile` build/cache metadata、hidden verifier logs、secret redaction、Docker run argument shape、hostless environment behavior、internal env override precedence、Harbor task env injection 和 external secret env injection。
- Verifier workspace mount temporary and writable。
- Hidden verifier logs admin-only。
- Harbor CPU/memory/network mapping。
- Harbor task text precedence。
- Harbor import declared safe task-relative source as editable source，缺失时 fallback empty source，且绝不 import `tests/`、`environment/`、`solution/`、verifier assets 或 task-private files。
- Harbor literal task env values 作为 `secret_env` 注入并参与 redaction。
- Placeholder rejection。
- Unsupported Windows tasks rejected。
- Unsupported multi-step tasks rejected。
- Unsupported Docker Compose、GPU、MCP、healthcheck、external service、storage、scheduling fields rejected。
- Unsupported raw Docker passthrough 和 task-declared extra host mounts rejected。
- `solution/` never becomes editable source。

SkyDiscover：

- Catalog add/update 默认使用 official URL 和 upstream `main`，支持 `--origin-url`、`--ref` 和 `--commit`，并总是存储 pinned exact commit。
- Catalog show does not fetch network。
- Catalog update dirty state failure。
- Catalog remove 仅 root 可执行，并在 active configs 或 open experiments bound to catalog-backed configs 引用 catalog tasks/evaluator bundles 时 blocked。
- Catalog removal 后 closed 和 archived experiment history 仍可 observe。
- SkyDiscover catalog add/update pin exact upstream commit，绝不自动 follow `main`。
- Missing catalog path does not auto-update。
- Missing active SkyDiscover catalog 失败，并给出 next action `catalog skydiscover add`；missing catalog paths 绝不 auto-fetch 或 auto-update。
- Source precedence：adapter project init 的 explicit editable source 仅限 `--source-path`、`--source-git` 或 `--source-empty`，并拒绝 `--source-ref`。
- 无 explicit source 时 initial program file import。
- 无 explicit source 时 initial program directory import。
- Missing initial program fails and asks for explicit source。
- 只导入 initial file/directory，不导入 whole benchmark。
- Docker evaluator parses top-level metrics。
- Docker evaluator fake-Docker coverage 证明 hidden evaluator bundle mount、workspace/program/run-dir env values、hostless environment、internal env override precedence、secret env injection，以及 hidden stderr redaction。
- Python evaluator uses wrapper subprocess，不在 main process import evaluator code。
- Python evaluator 作为 full V1 capability 覆盖，而不是 experimental/V2 deferred path。
- Python evaluator 在 safe root/admin summaries 中渲染 explicit non-OS-sandbox warnings。
- Python evaluator by dependency file hash create/reuse `uv` environment。
- Python evaluator environment cache key 包含 dependency file hashes、platform 和 Python version，dependency installation 可使用 default network。
- Cache prune root-only behavior 覆盖 Docker image caches、SkyDiscover evaluator environments 和 `--all`。
- Backup prune root-only behavior 覆盖 `--keep <n>` 和 `--older-than <days>`。
- Default SkyDiscover metric fallback averages finite numeric top-level metrics。
- Missing explicitly configured primary metric fails with `REWARD_PARSE_ERROR`。
- SkyDiscover search/proposal/mutation loops are not called。

## 8. Observe 和 Collaboration Tests

覆盖：

- Visibility `none`、`same_project`、`explicit` narrowing。
- Token context 始终可见自己的 experiment records；visibility scope 只控制其他 experiments。
- Effective token visibility 是 current project policy 与 experiment stored policy 的 intersection。
- Later project policy broadening 可以在 stored experiment policy bound 内 broaden existing token visibility。
- Public no-key `exp create --from-exp` visibility 是 current project public policy 与 source experiment stored visibility upper bound 的交集。
- Observe filters、pagination、sorting、best ranking。
- Invalid-project `best` 默认使用 active valid reward policy identity；没有 active valid config 时要求 explicit `--config-version`。
- Best ranking 排除 reward policy identity 不可比较的 runs，并渲染 `BEST_INCOMPARABLE_RUNS_EXCLUDED`。
- Best ranking 可跨 config version 比较 reward policy identity 相同的 runs，并排除 identity 不匹配的 runs。
- Search corpus 包含 allowed text，排除 logs/artifact bytes/history revisions。
- Archived experiments hidden by default from list/search/best。
- Tags add/remove/list by creator token and admin。
- Tags never grant visibility。
- Regenerated worktree token 对同一 experiment 的 experiment-private annotation 可见且可编辑，因为 private annotation ownership 绑定 experiment。
- Regenerated worktree token 继承自己 experiment 的 run、artifact 和 visible log archive/unarchive 权限。
- Annotation target parsing。
- Annotation `target_json` 存储 resolved target details。
- Annotation common commitish aliases and SHA resolution to concrete commit at creation。
- Annotation line validation。
- Current experiment shorthand path/line annotations 要求 clean worktree，并 anchor 到 HEAD。
- Root/admin project-context annotation body checks 使用 target experiment bound `secret_env` values。
- Project-context annotation target 如果不能精确 resolve 到一个 experiment，必须在 body storage 前拒绝。
- Private annotation visibility。
- Project-visible annotation 不会扩大 target visibility；caller 必须同时能按 normal visibility rules 看到 target record。
- Project visibility 后续 broaden 时 private annotation 仍保持 private。
- Annotation archive behavior。
- Annotation unarchive behavior。
- Annotation remove by creator/admin/root、archived-state requirement、revision deletion、audit event creation。
- Annotation revision history。
- Annotation body text/file-only input and stdin rejection。
- Inspection checkout creates detached HEAD and inspection token。
- Inspection observe/export uses pinned records when local files become dirty。
- Inspection tokens rejected for mutation commands。
- Hidden validation assets absent from experiment and inspection worktrees after project init/run/submit/checkout。
- Experiment/inspection tokens cannot view hidden verifier scripts、hidden test data、raw hidden logs、Harbor verifier bundles、SkyDiscover evaluator bundles through status/observe/artifacts/config summaries。
- Project remove with `--cascade` 作为 whole-tree operation 删除 archived project，不要求 child records 逐个 archived。
- Experiment remove with `--cascade` 删除 archived experiment 的 child runs、artifacts、logs、annotations、tags、inspection contexts、worktree 和 submission records，不要求这些 child records 逐个 archived。
- Source remove 保持 strict：config-version references 始终阻止 removal，experiment references 要求 dependent experiments archived 后 source cascade 才能继续。

## 9. Acceptance Gates

Core usable milestone ready when：

- Local auth、root regeneration、admin keys、credentials、context、local/Git/empty source import、project validation、experiment create、run、submit、observe basics、tags、annotations、logs、artifacts 在 macOS/Linux 上通过测试。
- Public/private collaboration boundaries 符合文档。
- Text output goldens 稳定。
- Raw root/admin keys 或 experiment tokens 不会在 creation/token-file rules 之外被存储或渲染；plaintext `secret_env` values 只保留在本地，且绝不渲染或 export。

Full V1 ready when：

- Docker runner 在 Docker available 时工作。
- Docker-dependent real-environment tests 通过 `ALAB_RUN_REAL_DOCKER=1` opt-in；当 Docker、daemon 或 required images 不可用时 skip，并覆盖 Docker image runner command and shell execution、real container environment isolation/internal `ALAB_*` overrides、Dockerfile runner build context and cache reuse、Harbor shared verifier、Harbor separate verifier image、Harbor separate `tests/Dockerfile`、Harbor real-container environment isolation/internal `ALAB_*` overrides/task-env/external secret injection、SkyDiscover Docker evaluator execution、SkyDiscover Docker real-container environment isolation/internal `ALAB_*` overrides/secret injection，以及 Dockerfile-backed adapter images 的 real Docker image-cache reuse。
- SkyDiscover Python real-environment dependency-installation tests 通过 `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1` opt-in；当 `uv` 不可用时 skip，并使用本地生成的 wheel，使 dependency path 可以在不需要 network access 的情况下验证。
- Networked SkyDiscover Python dependency-installation tests 通过 `ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1` opt-in；默认 skip，并通过 evaluator environment 从 configured package index 安装 direct 和 transitive pure-Python dependency cases。
- Native/binary SkyDiscover Python dependency-installation tests 通过 `ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1` opt-in；默认 skip，并通过 evaluator environment 从 configured package index 安装 native package。默认 package 是 `orjson>=3.10,<4`，也可通过 `ALAB_NATIVE_SKYDISCOVER_PYTHON_REQUIREMENT` 和 `ALAB_NATIVE_SKYDISCOVER_PYTHON_MODULE` 覆盖，以便做 platform-specific package-index validation。
- Live SkyDiscover catalog tests 通过 `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1` opt-in；当 `git` 或 official catalog remote 不可用时 skip，并验证 live clone/pin behavior、no-network `catalog show`，以及通过跳过 baseline validation 的 project init 解析真实 evaluator ref。
- Harbor single-step shared/separate verifier tasks 工作，unsupported Harbor features 清晰失败。
- SkyDiscover catalog、Docker evaluator、Python evaluator 工作。
- 所有 adapters 遵守 hidden validation asset rules。
- 完整 test suite 覆盖 local workflow、invalid project behavior、public/private permissions、source imports、run/submit behavior、observe、annotations、runner adapters、collaboration boundaries。
