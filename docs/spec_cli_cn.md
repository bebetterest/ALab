# ALab V1 CLI 规格

本文档是 [spec_cli.md](spec_cli.md) 的中文同步版。英文版是规范性来源；本文件保持同等决策内容。

## 1. 调用模型

Canonical invocation：

```text
alab [--home <path>] [--output text|rich] [--key <secret>] [--key-stdin] [<command> [args]]
```

规则：

- Global options 可以放在 canonical command 或 top-level alias 前后。
- CLI 必须先预扫描 argv 中的 global options，再执行 context detection、migration、config loading、credential lookup 或 command-specific parsing。
- Pre-scan 在第一个 standalone `--` 处停止。`--` 后的参数交给 command-specific parsing，绝不解释为 global `--home`、`--output`、`--key` 或 `--key-stdin`。
- 重复 global option 以 exit code `2` 失败，除非该 option 明确允许重复值。
- Command-local options 默认也只能出现一次。重复 command option 会在 command-specific writes、file exports、runner execution 或 lifecycle audit rows 之前以 `CONFIG_INVALID` 失败；只有明确记录为 repeated 的 option 例外，例如 experiment `--tag`、visibility `--visible-exp`、mutable-scope pattern options 和 submit `--ref`。
- 需要 value 的 global options 在 value 缺失、value 为空字符串，或下一个 token 是另一个 `--...` option 时，以 `CONFIG_INVALID` 失败。
- 需要 value 的 command-local options 在 value 缺失，或下一个 token 是另一个 `--...` option 时，以 `CONFIG_INVALID` 失败。Command-local structural values，例如 ids、selectors、paths、numeric values、choice values 和 file paths，也会对 empty strings 以 `CONFIG_INVALID` 失败。Direct user-text values，例如 body、summary、feedback、message、reason、author labels、goal text 和 query filters，在 field-specific validator 允许 empty text 时可以接受 empty string。这些检查发生在 command-specific file reads、writes、runner execution 或 lifecycle audit rows 之前。
- Command positional arguments 默认必须精确匹配命令语法。多余或缺失的 positional arguments 会通过共享 positional-count 或 single-selector validators 以 `CONFIG_INVALID` 失败，并且发生在 command-specific writes、file exports、runner execution 或 lifecycle audit rows 之前。
- Canonical nested command 是文档和测试的准绳。Alias 必须映射到同一 handler 和 result schema。
- 无 command 运行 `alab`、`alab help`、`alab --help` 或 nested command help request 时，进入 context-aware capability help surface。
- `--home` 在 context detection、migration、config loading、credential lookup 之前生效。
- `--output` 只选择单次命令的 rendering。
- `--key` 提供 root key 或 project admin key。
- `--key-stdin` 读取全部 stdin，最多去掉一个尾随换行，然后要求 non-empty single-line value 且不含 NUL byte。空输入、embedded newline 和 NUL byte 以 `CONFIG_INVALID` 失败。它与 `--key` 冲突。
- 只有没有 `--key` 和 `--key-stdin` 且命令需要 root/admin authorization 时才读取 `ALAB_KEY`。
- 空的 `ALAB_KEY` 按未设置处理，因此加载未填 key 的 `.env.example` 后，需要 credential 的命令仍应保持 `AUTH_REQUIRED` behavior。
- Public 或 optionally authorized 命令必须忽略 `ALAB_KEY` 的权限提升效果。只有显式提供 `--key` 或 `--key-stdin` 时，才可以渲染 authorized details。

Home 解析优先级：

1. `--home <path>`
2. `ALAB_HOME`
3. `~/.ALab`

Context-aware capability surface：

- ALab 保留一份 canonical command registry，但当前可见、可执行的 command surface 会按当前 context 和已验证 credential source 过滤。
- `alab`、`alab help`、`alab --help`、nested command help requests 和 command execution preflight 使用同一个 capability resolver。同一 argv、context 和 explicit credential 下，help output 与 command preflight 必须得到相同 allow/lock decision。
- Resolver 在 global option pre-scan、home resolution、migration、global config loading、context detection、explicit credential 或 context-token lookup 之后运行。它必须先于会读取用户 body/value files 的 command-specific parsing、Git 操作、除必要 read-only lookup 和 migration setup 以外的 SQLite 写入、runner execution 和 lifecycle audit row。
- 默认 capability 使用当前 context token；project context 未显式提供 key 时只暴露 public project capability。在任何 context 外，只把 global public commands 以及带 explicit target 且与当前 path 不冲突的 commands 作为候选。
- 显式 `--key` 或 `--key-stdin` 解锁匹配 credential surface：project admin key 解锁 same-project admin capability；root key 解锁 root capability。既有 context-conflict 规则仍生效，因此 root key 也不能在 cwd 位于另一个 active ALab context 时操作不同 explicit project。
- `ALAB_KEY` 不影响 `alab`、`alab help`、`alab --help`、nested command help 或任何 dynamic capability display。执行时，只有当命令已经在当前 context surface 中可用且要求 root/admin authorization 时，`ALAB_KEY` 才能继续满足 authentication。它不得把 experiment、inspection 或 public project surface 扩展成 admin/root surface。
- 用户直接调用当前 executable surface 外的命令时，ALab 以 `COMMAND_UNAVAILABLE` exit `4` 失败。这是 pre-handler availability failure，不替代 handler-level `AUTH_REQUIRED`、`AUTH_DENIED` 或 `SCOPE_VIOLATION`。
- Capability preflight 不是 authentication shortcut。如果命令在当前 context surface 中有效，但要求 root/admin credential，则缺失或无效 credential 仍使用既有 `AUTH_REQUIRED` 或 `AUTH_DENIED` contract。`COMMAND_UNAVAILABLE` 用于当前 context/token/public surface 完全不暴露的命令，例如没有 explicit admin/root key 时，在 experiment token surface 中执行 project config mutation。
- Locked commands 默认隐藏，以降低 agent 干扰。`alab help --all` 可以显示 locked commands，但 locked entries 只能使用安全的 reason 和 unlock hint；不得泄露 secret name/value、hidden log、hidden asset、absolute hidden path、不可见对象是否存在，或 private adapter staging path。

## 2. 输出模型

Command handler 返回 structured result object，由 renderer 转换为 CLI output。

V1 renderer：

- `text`：默认、可持久化、稳定、agent-friendly。
- `rich`：可选 human-friendly output，只能通过 `--output rich` 为单次命令启用。

V1 不暴露 `json`、`xml` 或隐藏实验性 structured output mode。Renderer boundary 可以在未来版本支持更多格式，但 V1 compatibility 只由 stable structured result object 渲染为 `text` 和单命令 `rich` 定义。

Global config path：

```text
~/.ALab/config.toml
```

Valid persisted global config：

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

- `format = "text"` 是唯一有效的 persisted output value。
- `format = "rich"` 以 `CONFIG_INVALID` 失败。
- Time values 使用 integer milliseconds。
- `storage.busy_timeout_ms` 配置 ALab database connections 使用的 SQLite `PRAGMA busy_timeout`。
- Persisted global config 在 top level 只接受 `schema_version`、`[output]`、`[storage]` 和 `[locks]`，并且每个 table 只接受 documented fields。Unknown keys 或 non-table section values 以 `CONFIG_INVALID` 失败。
- Invalid global config 在 home resolution 和 migration 后阻止 help 和 normal commands。`auth init` 和 `config show|set|reset|validate` 仍可用于 repair。
- Rich output 使用与 text output 相同的 result data，不得额外暴露 secret、hidden path、hidden log 或 hidden asset content。
- 默认禁用 Typer Rich help 和 pretty exception。
- Text output 是严格 key-value object 格式。每个 rendered object 以 `object: <type>` 开头。
- 每个 scalar field 渲染为 `field: value`。
- 多对象输出为重复 object block，中间严格用一个空行分隔。
- Nullable field 的 absent value 渲染为 `none`；用户文本中的 literal string `none` 绝不被转换为 null。
- Boolean 渲染为 `true` 或 `false`。
- List 一律渲染为 repeated labeled lines，每行一个 value，使用该命令 documented singular label。Empty list 不输出 repeated lines，除非 command result schema 明确包含 count 或 summary scalar。Text output 绝不使用 comma-separated list rendering。
- 多行 text field 渲染为 `field:`，随后每个内容行前加两个空格。Nullable multiline field 的 absent value 渲染为 `field: none`；non-null 空多行字符串渲染为 `field:` 后跟 `  [empty]`。
- 用户提供的 text fields，例如 task、goal、run message、submission summary、feedback 和 annotation body，一律使用 multiline text field 渲染。空用户文本渲染为 `field:` 后跟 `  [empty]`，从而区别于 nullable `none` 和 literal text `none`。
- Warning 在所有 primary result object 后以 `object: warning` block 渲染；每个 warning 一个 block，按产生顺序输出。
- Error output 也使用 object block。System/internal failure 渲染 `object: error`；saved result failure 渲染命令正常 result object，并附带 `error code`、`exit code`、`reason` 和 `next` fields。
- Help output 也从 structured capability result object 渲染。默认 help 只渲染 available commands。`--all` 可以在 available commands 后渲染 locked commands，并包含对当前 caller 安全的 locked reason 和 unlock hint fields。

## 3. Debug Mode

`ALAB_DEBUG=1` 只影响 internal/system failure。

允许：

- 打印正常 ALab error template。
- 打印 exception type。
- 打印完整 stack trace。

禁止：

- Locals 或 object dump。
- Environment map。
- Raw root key、admin key、experiment token。
- `secret_env` name/value pair、raw secret value、verifier hash。
- Hidden asset content。
- Raw hidden verifier/evaluator log。
- 会泄露 private asset 的 hidden staging path。

Result failure 不因 debug mode 打印 stack trace，例如 failed run 或 saved failed baseline。

## 4. Error、Warning 和 Exit Code

System/internal failure template：

```text
object: error
message: Command failed.
error code: PROJECT_INVALID
exit code: 4
project id: proj-example-a1b2
reason: project baseline validation is invalid
next: alab project validate --project proj-example-a1b2 --key <root-or-admin-key>
```

Result-failure 规则：

- 成功记录失败结果的命令 exit code 为 `1`。
- 例子：failed run、failed baseline validation、保存 record 的 timeout、submit not accepted。
- Result failure 输出相关 structured fields：id、status、reward parse status、log/artifact capture summary、stable error code、numeric exit code、reason、next action。
- 除非 ALab 自身无法执行流程，否则 result failure 不使用 internal/system failure template。

Warning output：

```text
object: warning
warning code: TOKEN_FILE_PERMISSIONS
warning reason: token file permissions are broader than 0600
```

Warning 是稳定 field，不是自由文本；一个命令可输出多个 warning。

V1 warning codes 包括：

- `TOKEN_FILE_PERMISSIONS`
- `TRACKED_SENSITIVE_SOURCE_FILE`
- `SOURCE_EMPTY_AFTER_FILTER`
- `SOURCE_DEDUPED_NAME_IGNORED`
- `PUBLIC_GIT_CREDENTIAL_HELPER_USED`
- `ENV_MODE_FULL_UNREDACTED_HOST_ENV`
- `ARTIFACT_BYTES_NOT_REDACTED`
- `ARTIFACT_CAPTURE_ERROR`
- `DOCKER_SETUP_OUTPUT_CAPTURED`
- `BEST_INCOMPARABLE_RUNS_EXCLUDED`
- `DOCKER_CACHE_PRUNE_FAILED`

Stable error codes：

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

Numeric exit codes：

| Exit code | Category | Examples |
| --- | --- | --- |
| 0 | success | command succeeded；run/validation/submit accepted |
| 1 | result failed | run failed；final submit not accepted；baseline failed；timeout with record saved |
| 2 | usage/config | invalid CLI arguments；schema invalid；bad TOML literal；source limit exceeded；duplicate name |
| 3 | auth | missing/invalid root/admin key；revoked key |
| 4 | context/scope | context conflict；scope violation；mutable violation；closed experiment |
| 5 | system/internal | storage failure；Git subprocess failure；runner could not start；migration failure |

Stable error-code exit mapping：

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
| `RUNNER_ERROR` | 有 saved run 或 validation record 时为 1；否则适用 `STORAGE_ERROR` 或 `GIT_ERROR` exit `5` |
| `REWARD_PARSE_ERROR` | 1 |
| `CONFIG_INVALID` | 2 |
| `BASELINE_VALIDATION_FAILED` | 1 |
| `OUTPUT_EXISTS` | 2 |
| `STORAGE_ERROR` | 5 |

规则：

- 每个 stable error code 都映射到上表 exit code。Command-specific matrix 可以补充常见 code 和 next action，但不得重新映射 exit。
- 未来所有 `*_NOT_FOUND` codes 默认 exit `2`。
- `COMMAND_UNAVAILABLE` 专用于 capability preflight。它表示当前 context 和 credential surface 不提供该命令。它必须在 command-specific side effects 之前返回，并且不得泄露 hidden object 是否存在。
- 有 saved run 或 validation record 的 result failure exit `1`，包括 runner start errors、Docker unavailable validation records、dependency installation failures，以及被捕获成最终 `error` status 的 adapter errors。
- 如果 ALab 无法创建或 finalize intended result record，command 使用 `STORAGE_ERROR`、`GIT_ERROR` 或其他适用 exit `5` code 作为 system/internal error 失败。

Input normalization 和 lookup rules：

- 所有 ALab object id 参数都要求完整 id，包括 home、project、source、experiment、run、validation、artifact、log、annotation、credential、token、audit、catalog 和 cache id。
- Git commit selector 可以使用完整 SHA；命令明确接受 commit selector 时，也可以使用无歧义的 abbreviated SHA。
- `--created-after`、`--created-before`、`--started-after`、`--ended-before` 等时间过滤参数只接受带 `Z` 或显式 numeric offset 的 RFC3339 timestamp。ALab 接受后统一 normalizes to UTC `Z` 再查询和输出。同一字段 family 同时提供 matching `after` 与 `before` 时，`after` 值必须小于或等于 `before` 值。
- 已存在且是目录的 export output path 会以 `OUTPUT_EXISTS` 失败，即使提供 `--overwrite`；`--overwrite` 只可替换文件，不可替换目录。
- `--value-file`、`--summary-file`、`--feedback-file` 和 `--body-file` 等 text input file options 在目标缺失、是目录、不可读或不是有效 UTF-8 时，以 `CONFIG_INVALID` 失败；这些失败发生在 secret writes、submission rows、annotation rows、runner execution 或 lifecycle audit rows 之前。
- Unknown object id 优先使用最具体的 `*_NOT_FOUND` code；没有对应 code 时，invalid selector/filter 使用 `CONFIG_INVALID`。
- Token-scoped 和 public caller 选择一个存在但对 caller 不可见的对象时，返回 `SCOPE_VIOLATION`，reason 使用非泄露表述，例如 `not visible or not found`。Public/token-scoped output 不得泄露对象是否存在于 caller visibility 之外。Root/admin caller 使用精确的 `*_NOT_FOUND` 或 scope error。

Command error matrix：

- 所有命令在 storage、migration、backup 或 unexpected SQLite failure 时都可以以 `STORAGE_ERROR` 和 exit code `5` 失败。
- 所有运行 Git 的命令都可以以 `GIT_ERROR` 和 exit code `5` 失败；在 Git mutation 前验证 user worktree state 的命令使用 `GIT_STATE_INVALID` 和 exit code `4`。
- 所有要求 root/admin credential 的命令都可以以 `AUTH_REQUIRED` 或 `AUTH_DENIED` 和 exit code `3` 失败。
- 所有 token-scoped 命令都可以按场景以 `AUTH_REQUIRED`、`AUTH_DENIED`、`CONTEXT_NOT_FOUND`、`CONTEXT_CONFLICT` 或 `SCOPE_VIOLATION` 失败。
- 除 help 外的所有 command 在 context-aware capability resolver 于 handler execution 前拒绝命令时，都可以以 `COMMAND_UNAVAILABLE` exit `4` 失败。
- 写 lifecycle audit event 的命令成功时渲染 `audit id`，除非 command-specific secret rule 明确禁止。

| Command family | Stable failure codes |
| --- | --- |
| `help`、无 command `alab`、`--help`、nested command help | `COMMAND_UNAVAILABLE` 不适用；invalid help selector 或 invalid global config 使用 `CONFIG_INVALID` exit `2`；`STORAGE_ERROR` exit `5` |
| `auth init` | `HOME_EXISTS` exit `2`；`STORAGE_ERROR` exit `5` |
| `auth root regenerate` | `AUTH_REQUIRED`、`AUTH_DENIED` exit `3`；`STORAGE_ERROR` exit `5` |
| `config show|set|reset|validate` | `CONFIG_INVALID` exit `2`；`STORAGE_ERROR` exit `5` |
| `key create|list|revoke` | `AUTH_REQUIRED`、`AUTH_DENIED` exit `3`；`PROJECT_NOT_FOUND`、`CREDENTIAL_NOT_FOUND` 或 `CONFIG_INVALID` exit `2` |
| `context show|repair` | `CONTEXT_NOT_FOUND` exit `2`；`CONTEXT_CONFLICT`、`SCOPE_VIOLATION` exit `4`；`AUTH_REQUIRED`、`AUTH_DENIED` exit `3`；invalid path `CONFIG_INVALID` exit `2` |
| `project list|show|status` | `AUTH_REQUIRED`、`AUTH_DENIED` exit `3`；`PROJECT_NOT_FOUND` exit `2`；`CONTEXT_CONFLICT` exit `4` |
| `project archive|unarchive` | `PROJECT_NOT_FOUND` exit `2`；`RESOURCE_BUSY` exit `4`；auth failures exit `3`；已经处于目标 archive state 时 exit `0` |
| `project remove` | missing confirmation `CONFIG_INVALID` exit `2`；`PROJECT_NOT_FOUND` exit `2`；not archived 或 blockers `RESOURCE_BUSY` exit `4`；auth failures exit `3` |
| `project init` | invalid config `CONFIG_INVALID` exit `2`；invalid/conflicting source `SOURCE_INVALID` exit `2`；failed baseline `BASELINE_VALIDATION_FAILED` exit `1`；auth failures exit `3` |
| `project config/env/secret` | invalid field/value/retain marker `CONFIG_INVALID` exit `2`；missing active valid version `PROJECT_INVALID` exit `4`；baseline failure `BASELINE_VALIDATION_FAILED` exit `1`；auth failures exit `3`；export target exists 时 `OUTPUT_EXISTS` exit `2` |
| `project validate` | failed/error/timeout validation `BASELINE_VALIDATION_FAILED` exit `1`；`PROJECT_NOT_FOUND` exit `2`；auth failures exit `3` |
| `project validation archive|unarchive|remove` | `PROJECT_NOT_FOUND`、`VALIDATION_NOT_FOUND` 或 `CONFIG_INVALID` exit `2`；active/not archived/blockers `RESOURCE_BUSY` exit `4`；auth failures exit `3`；已经处于目标 archive state 时 exit `0` |
| `project locks clear-stale` | `PROJECT_NOT_FOUND` exit `2`；auth failures exit `3` |
| `backup prune` | invalid retention selector `CONFIG_INVALID` exit `2`；auth failures exit `3` |
| `audit list|show` | invalid filters `CONFIG_INVALID` exit `2`；`AUDIT_NOT_FOUND` exit `2`；auth failures exit `3` |
| `source import` | `SOURCE_INVALID`、`SOURCE_LIMIT_EXCEEDED`、`NAME_CONFLICT` exit `2`；`PROJECT_NOT_FOUND` exit `2`；auth failures exit `3` |
| `source list|show` | `SOURCE_NOT_FOUND` 或 `PROJECT_NOT_FOUND` exit `2`；auth failures exit `3` |
| `source archive|unarchive|remove` | `SOURCE_NOT_FOUND`、`CONFIG_INVALID` exit `2`；active default、not archived 或 blockers `RESOURCE_BUSY` exit `4`；auth failures exit `3`；已经处于目标 archive state 时 exit `0` |
| `catalog skydiscover add|update|show|remove` | invalid selector、dirty catalog 或 existing catalog `CONFIG_INVALID` exit `2`；`CATALOG_NOT_FOUND` exit `2`；active references `RESOURCE_BUSY` exit `4`；auth failures exit `3` |
| `cache prune` | invalid selector combination `CONFIG_INVALID` exit `2`；auth failures exit `3` |
| `exp create` | invalid source/name/path `CONFIG_INVALID`、`SOURCE_INVALID` 或 `NAME_CONFLICT` exit `2`；invalid project state `PROJECT_INVALID` 或 `PROJECT_ARCHIVED` exit `4`；auth failures exit `3` |
| `exp archive|unarchive|remove` | `EXPERIMENT_NOT_FOUND` 或 `CONFIG_INVALID` exit `2`；active lock/not archived/blockers `RESOURCE_BUSY` exit `4`；auth failures exit `3`；已经处于目标 archive state 时 exit `0` |
| `exp checkout|checkout remove` | invalid path/commit/selector `CONFIG_INVALID` exit `2`；visibility/scope failures `SCOPE_VIOLATION` exit `4`；auth failures exit `3` |
| `exp worktree remove|restore` | invalid path/confirmation `CONFIG_INVALID` exit `2`；cleanup failure 或 context nesting `RESOURCE_BUSY`/`CONTEXT_CONFLICT` exit `4`；auth failures exit `3` |
| `exp token list|revoke|regenerate` | invalid selector `CONFIG_INVALID` exit `2`；`EXPERIMENT_NOT_FOUND` 或 `CREDENTIAL_NOT_FOUND` exit `2`；auth failures exit `3` |
| `exp tag add|remove|list` | invalid tag `CONFIG_INVALID` exit `2`；scope failures `SCOPE_VIOLATION` exit `4`；auth failures exit `3` |
| `run` | failed/error/timeout run `RUNNER_FAILED`、`RUNNER_ERROR`、`RUNNER_TIMEOUT` 或 `REWARD_PARSE_ERROR` exit `1`；mutable violations `SCOPE_VIOLATION` exit `4`；invalid Git state `GIT_STATE_INVALID` exit `4`；busy experiment `EXPERIMENT_BUSY` exit `4` |
| `submit` | final run not accepted `RUNNER_FAILED`、`RUNNER_ERROR`、`RUNNER_TIMEOUT`、`REWARD_PARSE_ERROR` 或 missing reusable run exit `1`；invalid refs/inputs `CONFIG_INVALID` exit `2`；closed/scope failures exit `4` |
| `observe experiments|runs|artifacts|logs|annotations` | invalid filters/sort/selector `CONFIG_INVALID` exit `2`；root/admin 下 object not found 使用 matching `EXPERIMENT_NOT_FOUND`、`RUN_NOT_FOUND`、`ARTIFACT_NOT_FOUND`、`LOG_NOT_FOUND` 或 `ANNOTATION_NOT_FOUND` exit `2`；token/public not-visible-or-not-found selector `SCOPE_VIOLATION` exit `4`；export target `OUTPUT_EXISTS` exit `2`；auth failures exit `3`；archive/unarchive 已经处于目标状态时 exit `0` |
| `annotate add|edit|archive|unarchive|remove` | invalid target/body/confirmation `CONFIG_INVALID` exit `2`；root/admin 下 `ANNOTATION_NOT_FOUND` exit `2`；token/public not-visible-or-not-found selector 和其他 visibility/scope failures `SCOPE_VIOLATION` exit `4`；auth failures exit `3`；archive/unarchive 已经处于目标状态时 exit `0` |

## 5. Context 和 Credential 术语

Context：

- Global：不需要 project 或 experiment context。
- Project：project control directory 或显式 `--project`。
- Experiment：带 `.alab/context.json` 和 `.alab/token` 的 registered experiment worktree。
- Inspection：由 `exp checkout` 创建的 read-only ALab context。
- Any：home resolution 后任何路径都可运行。

Credential：

- None：不需要 key/token。
- Root：root key。
- Admin：project admin key。
- Root/admin：root key 或匹配 project admin key。
- Token：有效 worktree 或 inspection token，取决于命令。
- Public：project policy 允许时无需 key。

Capability surface terms：

- Available：命令会出现在默认 help 中，并且可以在正常 command-specific parsing 后进入 command handler。
- Locked：命令存在于 canonical registry，但 active context、credential source、project policy 或 token mode 当前不暴露该命令。
- Hidden：locked commands 默认从 help 中省略。它们只在 `alab help --all` 中出现，并且只带安全的 locked reason 和 unlock hint。
- Credential source：取值为 `none`、`public`、`context-token`、`explicit-admin`、`explicit-root` 或 `ambient-env`。`ambient-env` 绝不用于 help capability display，也绝不扩展 token 或 public context surface。
- Capability source：使命令 available 的规则，例如 `global`、`public-project`、`worktree-token`、`inspection-token`、`project-admin` 或 `root`。

Default context surfaces：

- Global 且无 explicit key：显示 `help`、`auth init`、config diagnostics/repair，以及不要求 project record 的 context diagnostics commands。要求 project 的 command 只有在提供 explicit target 且不与当前 path 冲突时才可能 available。
- Global 且带 explicit project admin key：显示匹配 project 的 admin surface，以及可通过显式传入该 project id 运行的 commands。
- Global 且带 explicit root key：额外显示 root-level project creation、project listing、key management、catalog、cache、backup 和 audit commands。
- Project context 且无 explicit key：显示 public safe `status`；当 project policy 允许 public experiment creation 时，显示 public `exp create` 和 source bootstrap。隐藏 project management、source management、config、validation、audit、cache、catalog、backup、key 和 lifecycle maintenance commands。
- Project context 且带 explicit project admin key：显示同 project 的 project/source/config/validate/observe/experiment management commands，但不显示 root-only commands。
- Project context 且带 explicit root key：显示 project admin capabilities 以及 scope 内的 root-only commands。
- Experiment context 且使用 worktree token：显示 `status`、`run`、`submit`、visible observe commands、own-experiment tag commands、authorized annotations，以及 own-experiment run/artifact/visible-log archive 或 unarchive commands。隐藏 project/source/config/project init、experiment remove、worktree maintenance、key management、audit、cache、catalog 和 backup commands。
- Experiment context 且带 explicit project admin 或 root key：解锁匹配的 same-project admin 或 root surface，同时保留对不同 explicit project 的既有 context-conflict rules。
- Inspection context 且使用 inspection token：显示 `status`、visible observe commands、artifact/log export，以及移除自己的 inspection checkout。隐藏 run、submit、tag mutation、annotation mutation、project/source/config management、experiment mutation、worktree maintenance、key management、audit、cache、catalog 和 backup commands。
- Inspection context 且带 explicit project admin 或 root key：解锁匹配的 same-project admin 或 root surface；没有 explicit key 时仍保持 inspection-token read-only 行为。

## 6. Command Group 和 Alias

Canonical groups：

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

Top-level aliases：

- 无 command 的 `alab` 和 `alab --help` 映射到 `alab help`。
- `alab status` 映射到 project/experiment/inspection status。
- `alab run` 是 experiment run 的 canonical top-level command。
- `alab submit` 是 experiment submit 的 canonical top-level command。
- `alab exp list|search|show|best` 映射到 `observe experiments ...`。
- `alab runs list|show|archive|unarchive|remove` 映射到 `observe runs ...`。
- `alab artifacts list|show|export|archive|unarchive|remove` 映射到 `observe artifacts ...`。
- `alab logs list|show|export|archive|unarchive|remove` 映射到 `observe logs ...`。
- `alab annotations list|show` 映射到 `observe annotations ...`。

Alias policy：

- V1 只支持本节列出的 aliases。
- `alab run` 和 `alab submit` 是 canonical top-level commands；V1 不新增 `alab exp run` 或 `alab exp submit` alias。
- Help aliases 在 rendering 前使用 capability resolver。它们不使用 ambient `ALAB_KEY` 扩展 visible surface。
- 未来任何 alias 都必须映射到 existing handler 和 structured result schema，并在接受前添加 golden tests。

## 7. Command Contract 总则

每个命令都必须有 golden tests 覆盖 text success output、text error output、alias behavior，以及 command 前后 global option placement。

以下 command contracts 是规范性的 text-output schema：

- `Object type` 指 primary result block 的精确 `object: <type>` 值。
- `Success fields` 按列出顺序渲染；renderer 不得重排字段、添加 storage-only fields，或省略非空 listed fields，除非 command-specific rule 标记为 conditional。
- `Success fields per <type>` 表示命令渲染零个或多个 `object: <type>` blocks，每个 row 一个 block，字段顺序按列表。
- Repeated fields 使用 command contract 命名的 singular label，每个 value 一行。Repeated object rows 渲染为独立 object blocks。
- Dry-run remove command 使用与 actual remove 相同的 object type，并在 base success fields 后按 golden tests 定义的稳定顺序追加 blocker 和 count fields。
- Saved result failure，例如有 saved row 的 failed run 或 validation，使用命令正常 primary object type 和 field order，然后追加 `error code`、`exit code`、`reason` 和 `next` fields。
- System/internal failure 只使用前文定义的 `object: error`。Warning 永远在 primary result objects 后以 `object: warning` 渲染。

Primary object types：

| Command pattern | Object type |
| --- | --- |
| `help`、无 command `alab`、`--help` 和 nested command help | `help` |
| help output 的 repeated command rows | `help_command` |
| `auth init`, `auth root regenerate` | `auth` |
| `config show|set|reset|validate` | `config` |
| `config validate` 的 repeated capability rows | `capability` |
| `key create|list|revoke`, `exp token list|revoke|regenerate` | `credential` |
| `context show|repair` | `context` |
| `project init`, `project list|show|archive|unarchive|remove`, project/public mode 的 `status` | `project` |
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
| `exp create|list|search|show|best|archive|unarchive|remove`, experiment mode 的 `status` | `experiment` |
| `exp checkout`, `exp checkout remove`, inspection mode 的 `status` | `inspection_checkout` |
| `exp worktree remove|restore` | `worktree` |
| `exp tag add|remove|list` | `tag` |
| `run`, `observe runs list|show|archive|unarchive|remove` | `run` |
| `submit` | `submission` |
| `observe artifacts list|show|export|archive|unarchive|remove` | `artifact` |
| `observe logs list|show|export|archive|unarchive|remove` | `log` |
| `annotate add|edit|archive|unarchive|remove`, `observe annotations list|show` | `annotation` |

Lifecycle command rules：

- Archive 和 unarchive command 是幂等的。对已经处于请求状态的 object 重复操作时 exit `0`，渲染 unchanged state，并且不创建重复 audit event。
- `remove --dry-run` 即使 target 未 archived 也 exit `0`，渲染稳定的 `target_not_archived` blocker，且绝不写 audit row 或删除数据。
- Actual `remove` 在 target 未 archived 时仍然失败。

命令契约必须包含：

- required context；
- accepted credential scope；
- required arguments；
- optional arguments and defaults；
- mutually exclusive arguments；
- result-failure exit behavior；
- stable text output fields。

## 8. Help、Auth 和 Key Commands

`alab help [--all] [--explain]`、无 command `alab`、`alab --help` 和 nested command help requests

- Context：Any。
- Credential：None、context token 或 explicit root/admin key。
- Options：`--all`、`--explain`。
- Ambient env rule：忽略 `ALAB_KEY` 的 capability display 影响。
- Availability rule：default help 只包含当前 context 和 credential source 可用的 commands。
- Full listing rule：`--all` 在 available commands 后包含 locked commands，并带安全 locked reason 和 unlock hint。
- Explanation safety rule：`--explain` 渲染 context 和 credential-source explanation fields，但不得渲染 raw token、raw key、secret name/value、verifier hash、hidden log content、hidden asset content、不可见对象是否存在，或 private adapter staging path。
- Success fields：`context type`、`credential source`、`credential scope`、`project id`、`exp id`、`mode`、repeated `next`。
- Success fields per `help_command`：`command`、`available`、`locked reason`、`unlock hint`、`capability source`、`summary`。
- Default rule：只为 available commands 渲染 `help_command` object。
- `--all` rule：额外渲染 locked `help_command` objects，字段包含 `available: false`、安全的 `locked reason` 和安全的 `unlock hint`。
- `--explain` rule：包含 `capability source` 和任何安全 explanatory `summary`；没有 `--explain` 时，`capability source` 可以渲染为 `none`。
- Exit：成功 `0`；invalid help options/selectors 或 invalid global config `2`；storage failure `5`。

`alab auth init`

- Context：Any。
- Credential：None。
- Required args：无。
- Conflicts：home 已初始化，或目标 path 已存在且是非空、非 ALab home 的 directory。
- Success fields：`home`、`home id`、`root key`、`created`。
- Exit：创建成功 `0`；home 已初始化时以 `HOME_EXISTS` 和 exit code `2` 失败；storage failure `5`。
- Secret：raw root key 只打印一次。

`alab auth root regenerate`

- Context：Any。
- Credential：Root。
- Success fields：`home`、`home id`、`root key`、`revoked key id`、`created key id`。
- Exit：成功 `0`；auth failure `3`；storage failure `5`。
- Secret：replacement root key 只打印一次。

`alab config show`

- Context：Any。
- Credential：None。
- Success fields：`home`、`schema version`、`output format`、`preview bytes`、`busy timeout ms`、`lock acquire timeout ms`、`lock heartbeat interval ms`、`lock stale after ms`、`config valid`。

`alab config set <field> <toml-literal>`

- Context：Any。
- Credential：None。
- Required args：dotted `field` 和 TOML literal `value`。
- Allowed fields：`output.format`、`output.preview_bytes`、`storage.busy_timeout_ms`、`locks.acquire_timeout_ms`、`locks.heartbeat_interval_ms` 和 `locks.stale_after_ms`。
- `output.format` 只能设置为 TOML string `"text"`；其他值以 `CONFIG_INVALID` 失败。
- Repair rule：可修复 partially valid config 中的 known field；TOML 无法解析时，next action 指向 `alab config reset --all`。
- Success fields：`field`、`previous value`、`value`、`config valid`。

`alab config reset <field>|--all`

- Context：Any。
- Credential：None。
- Required args：exactly one field 或 `--all`。
- Success fields：`reset`、`field`、`value`、`config valid`。

`alab config validate [--refresh-capabilities]`

- Context：Any。
- Credential：None。
- Options：`--refresh-capabilities`。
- Success fields for object `config`：`config valid`、`next`。
- Success fields for object `capability`：`capability`、`fingerprint`、`status`、`checked at`、`next`。
- 当 global config invalid 时，这组命令仍可运行以修复配置。

`alab key create --project <project_id> [--role admin]`

- Context：Any 或 Project。
- Credential：Root。
- Required args：`--project`。
- Defaults：`--role admin`。
- Options：`--role` 接受 `admin`。
- Success fields：`project id`、`key id`、`role`、`admin key`、`created`。
- Secret：raw admin key 只打印一次。

`alab key list --root`

- Context：Any。
- Credential：Root。
- Required args：`--root`。
- Conflicts：`--project`。
- Success fields per key：`key id`、`credential type`、`status`、`created at`、`revoked at`。
- Secret rule：不得包含 raw secret 或 verifier hash。

`alab key list --project <project_id>`

- Context：Any 或 Project。
- Credential：Root/admin。
- Required args：`--project`，除非 project context 已提供。
- Conflicts：`--root`。
- Success fields per key：`project id`、`key id`、`role`、`status`、`created at`、`revoked at`。
- Secret rule：不得包含 raw secret 或 verifier hash。

`alab key revoke <key_id> [--project <project_id>]`

- Context：Any 或 Project。
- Credential：Root。
- Success fields：`key id`、`status`、`revoked at`。
- 不通过此命令 revoke 唯一 active root key。

## 9. Context Commands

`alab context show [--path <dir>]`

- Context：Any。
- Credential：无 credential 可显示 local marker summary；full registry details 需要 Root/admin 或匹配 token。
- Defaults：`--path .`。
- Success fields：`path`、`resolved path`、`home id`、`context type`、`project id`、`exp id`、`token id`、`registered`、`path status`、`next`。

`alab context repair --path <dir>`

- Context：Any。
- Credential：Root/admin，或满足 strict self-repair 条件的 valid token。
- Required args：`--path`。
- Success fields：`path`、`resolved path`、`context type`、`project id`、`exp id`、`repair mode`、`status`。

## 10. Project Commands

`alab project list [--include-archived]`

- Context：Any。
- Credential：Root。
- Success fields：每个 project 输出 `project id`、`project name`、`project status`、`created at`、`updated at`、`archived at`。

`alab project show [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields：`project id`、`home id`、`project name`、`status`、`task`、`goal`、`active config version`、`latest attempted config version`、`default source`、`runner type`、`sandbox`、`reward type`、`visibility scope`、`mutable summary`、`public exp create`。
- Sandbox rule：SkyDiscover Python runners 的 `sandbox` 是 `not-os-sandbox`，其他 runner 是 `not-declared`。
- Exit：成功 `0`；auth failure exit `3`；missing context 使用 `CONTEXT_NOT_FOUND` exit `2`。

`alab project archive [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields：`project id`、`previous status`、`project status`、`archived at`。
- Archive 遇到 active validation、source import、run、submit、worktree maintenance 或 project maintenance lock 时以 `RESOURCE_BUSY` 失败。

`alab project unarchive [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields：`project id`、`previous status`、`project status`、`unarchived at`。

`alab project remove [--project <project_id>] (--dry-run|--force --confirm <project_id>) --cascade [--reason <text>]`

- Context：Project 或 explicit project。
- Credential：Root。
- Required args：`--cascade`，以及 `--dry-run` 或 `--force` 加 matching `--confirm`。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields：`project id`、`dry run`、`removed`、`cascade`、`audit id`、repeated `blocker`、`deleted experiments`、`deleted runs`、`deleted artifacts`、`deleted logs`、`deleted sources`、`deleted filesystem paths`、dry-run repeated `filesystem path` 和 `planned trash move`、actual-run `trash cleanup pending`。
- Dry run 输出 blocker、deletion count、受影响 filesystem path 和 planned trash move，不写 audit row，不删除数据；target 未 archived 时输出 `target_not_archived` blocker 并 exit `0`。
- Cascade rule：project remove 是 whole-tree deletion operation，因此 project 自身 archived 且不存在 active locks 后，child project records 不需要逐个 archived。
- Trash rule：actual remove 会先把 project root、project control path，以及 active registered worktree/inspection path stage 到 ALab trash，再做 DB/audit mutation。Project credential 和 token row 会 revoke 并保留；path registry row 会标记为 `removed` 并保留。
- Project 必须 archived；cascade blocker 以 context/scope failure 失败。

`alab status [--project <project_id>]`

- Context：Project、Experiment、Inspection 或 explicit project。
- Credential：Public safe summary、project context 中 Root/admin、experiment/inspection context 中 Token。
- Success fields for scope `project|public`：`context type`、`project id`、`project status`、`task`、`next`。
- Success fields for scope `experiment|inspection`：`context type`、`project id`、`project status`、`task`、`next`、`exp id`、`experiment status`。
- Success fields for scope `public-invalid`：`context type`、`project id`、`project status`、`next`。
- Public-invalid output 适用于 no-key public/project status，也适用于有效但未授权 target project、且通过 public status surface 放行的 explicit credentials。
- Public status 不得包含 history、env values、secret names/values、full runner command、hidden assets、hidden logs、absolute catalog/staging paths。
- V1 没有独立的 project-private status switch。`project.allow_public_exp_create = false` 只禁用 public experiment creation；不会禁用 public safe status。
- Exit：`0`；project not found 为 `2`；explicit credential auth failure 为 `3`；context conflict 为 `4`。

`alab project init local|git|empty|harbor|skydiscover ...`

- Context：Any。
- Credential：Root。
- Required args：`--config` 和 mode-specific source/task fields。
- Common options：`--name`、`--task`、`--goal`、`--config`、`--skip-baseline-test`。
- Source limit options：`--max-files`、`--max-total-bytes`、`--max-file-bytes`；values 必须是 non-negative integers。
- Source conflicts：每个 init mode 只有一个 source origin，除非 adapter source precedence 明确允许同时出现。
- Harbor 和 SkyDiscover init source rule：V1 拒绝 `--source-ref`；adapter init 的 explicit editable source 必须是 `--source-path`、`--source-git` 或 `--source-empty`，否则使用 adapter-derived source。
- Adapter source rule：如果 adapter-derived editable source 和 explicit caller source 同时存在，canonical tree hash 相同则正常 dedupe；不同则以 `SOURCE_INVALID` 失败，不静默覆盖。
- Config source rule：input config 如果包含 `source.default_source_ref`，必须匹配 staged canonical source ref；不匹配以 `CONFIG_INVALID` 失败。省略时由 init 注入 canonical source ref。
- Runtime config rule：runner、reward、artifact、log、env、secret、Docker、Harbor 和 SkyDiscover fields 只从 config 读取。V1 init 不暴露 runtime flags。
- Success fields：`project id`、`project name`、`project status`、`source id`、`source ref`、`config version`、`validation id`、`validation status`、`admin key`、repeated `warning code`、`next`。
- Secret rule：project record 写入时始终创建一个 project admin key，并只打印一次 raw admin key，包括随后 baseline failed 而保留 invalid project 的情况。
- Exit：validation passed 或 skipped 为 `0`；project 已创建但 baseline failed 为 `1`；invalid config/source 为 `2`；auth failure 为 `3`。

`alab project config show [--project <project_id>] [--version latest-attempted|active-valid|<n>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- 默认 `--version latest-attempted`；`active-valid` 在无 active valid config 时以 `PROJECT_INVALID` 失败；显式 `<n>` 必须是正整数 retained config version number。
- Success fields：`project id`、`config version`、`version selector`、`config hash`、`project name`、`task`、`goal`、`default source`、`runner type`、`sandbox`、`runner working directory`、`timeout seconds`、`env mode`、`reward type`、`reward direction`、`primary metric`、`artifact glob count`、`stdout limit bytes`、`stderr limit bytes`、`mutable summary`、`visibility scope`、`public exp create`、repeated `env name`、repeated `secret name`、repeated `secret fingerprint`。
- Sandbox rule：SkyDiscover Python runners 的 `sandbox` 是 `not-os-sandbox`，其他 runner 是 `not-declared`。
- Secret rule：绝不打印 raw secret values。

`alab project config export --out <path> [--overwrite] [--project <project_id>] [--version latest-attempted|active-valid|<n>]`

- 默认 `--version latest-attempted`；`active-valid` 在无 active valid config 时以 `PROJECT_INVALID` 失败；显式 `<n>` 必须是正整数 retained config version number。
- 默认 target exists 时以 `OUTPUT_EXISTS` 失败；`--overwrite` 替换。
- Conflicts：target exists 且未提供 `--overwrite`。
- Success fields：`project id`、`config version`、`out`、`wrote`、`secret mode`。
- Secret rule：export 只写 retain marker 和 secret fingerprint，绝不写 raw secret value。

`alab project config import --config <path> [--project <project_id>] [--dry-run] [--skip-baseline-test]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Conflicts：`--dry-run` 与 `--skip-baseline-test` 冲突。
- Dry-run 只 parse/canonicalize config、计算 diff、报告是否需要 baseline，并运行 runtime capability checks；不写 DB、不创建 audit row、不改文件、不执行 baseline runner。
- Success fields：`project id`、`previous active config version`、`latest attempted config version`、`runtime affecting`、`validation status`、`project status`、repeated `warning code`、`next`。
- Runtime change 的 exit 行为跟 baseline result 一致。

`alab project config set <field> <value> [--project <project_id>] [--dry-run] [--skip-baseline-test]`

- 支持任意非 secret field 的 TOML literal，包括 scalar、array 和 map。
- 设置 array 或 map 会替换完整 field；V1 不做 nested value deep merge。
- `[secret_env]` 必须通过 `project secret` 或 config import retain markers 修改。
- 基于 latest attempted config 编辑；metadata-only edit 不能让 invalid runtime config 变 valid。
- Conflicts：`--dry-run` 与 `--skip-baseline-test` 冲突。
- Dry-run 规则与 config import 相同。
- Success and exit follow config import.

`alab project env set|unset|list ...`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Required args：`set <name> <value>`，`unset <name>`，`list` 无参数。
- Rule：`<name>` 必须匹配 `^[A-Za-z_][A-Za-z0-9_]*$`。
- Success fields for `set|unset`：`project id`、`config version`、`env name`、`action`、`runtime affecting`、`validation status`。
- Success fields per env for `list`：`project id`、`config version`、`env name`、`value`。
- Exit follows config import for mutating commands；`list` exits `0`。

`alab project secret set|unset|list|gc ...`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Required args：`set <name> --value-stdin|--value-file <path>`，`unset <name>`，`list` 无参数，且 `gc --dry-run` 或 `gc --apply` 必须恰好一个。
- Conflicts：`--value-stdin` 与 `--value-file`；`gc --dry-run` 与 `gc --apply`。
- Rule：`<name>` 必须匹配 `^[A-Za-z_][A-Za-z0-9_]*$`。
- Secret input rule：`--value-stdin` 和 `--value-file` 读取完整 input，最多去掉一个尾随换行，然后要求 non-empty single-line UTF-8 value 且不含 NUL byte。空值、embedded newline 和 NUL byte 以 `CONFIG_INVALID` 失败；短于 4 UTF-8 bytes 的值按 storage secret-value rule 以 `CONFIG_INVALID` 失败。
- Rule：`gc --dry-run` 只输出 unreferenced secret value candidates，不删除数据、不写 audit row；`gc --apply` 只删除未引用的 raw secret values，并写 audit event。
- Success fields for `set|unset`：`project id`、`config version`、`secret name`、`action`、`secret fingerprint`、`runtime affecting`、`validation status`。
- Success fields per secret for `list`：`project id`、`secret name`、`secret fingerprint`、`referenced`、`created at`、`replaced at`。
- Success fields for `gc`：`project id`、`dry run`、`deleted count`、repeated `secret value id`、`audit id`。
- Secret rule：绝不输出 raw secret values。
- Exit follows config import for mutating commands。

`alab project validate [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields：`project id`、`validation id`、`config version`、`validation status`、`exit code`、`reward`、`reward parse status`、`project status`、repeated `warning code`、`next`。

`alab project validation archive|unarchive <validation_id> [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields for `archive`：`project id`、`validation id`、`previous archive status`、`archive status`、`archived at`、`audit id`。
- Success fields for `unarchive`：`project id`、`validation id`、`previous archive status`、`archive status`、`unarchived at`、`audit id`。

`alab project validation remove <validation_id> [--project <project_id>] (--dry-run|--force --confirm <validation_id>) [--cascade] [--reason <text>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- `remove` 需要 `--dry-run` 或 `--force --confirm <validation_id> [--cascade] [--reason <text>]`。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields：`project id`、`validation id`、`dry run`、`removed`、`cascade`、`audit id`、repeated `blocker`、`deleted artifacts`、`deleted logs`、`active dependent artifacts`、`active dependent logs`、`deleted filesystem paths`、dry-run repeated `filesystem path` 和 `planned trash move`、actual-run `trash cleanup pending`。
- Remove cascade rule：带 dependent artifact 或 log row 的 archived validation 在未传 `--cascade` 时输出 `dependent_records_require_cascade`；传入 `--cascade` 后，active dependent artifact/log row 会输出 `dependent_records_not_archived`；已 archived 的 dependent row 会在同一个 audited operation 中删除，未共享文件会在 DB mutation 前 stage 到 ALab trash。
- Active validation 不能 archive/remove。

`alab project locks clear-stale`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields：`project id`、`cleared count`、清理的 repeated `lock name`、`audit id`。

`alab backup prune (--keep <n>|--older-than <days>)`

- Context：Any。
- Credential：Root。
- `--keep` 与 `--older-than` 二选一且冲突。
- Bounds：`--keep` 和 `--older-than` 必须大于等于 `0`。
- Success fields：`backup pruned count`、repeated `backup path`、`audit id`。

## 10A. Audit Commands

`alab audit list [--project <project_id>] [filters]`

- Context：Any 或 Project。
- Credential：global audit 需要 Root；project-scoped audit 需要 Root/admin。
- Filters：`--object-type`、`--object-id`、`--action`、`--actor`、`--created-after`、`--created-before`、`--limit`、`--offset`。
- Bounds：`--limit` 必须在 `1` 到 `1000` 之间；`--offset` 必须大于等于 `0`。
- `--object-type` values 是 audit object types：`annotation`、`artifact`、`backup`、`cache`、`catalog`、`credential`、`experiment`、`inspection_checkout`、`lock`、`log`、`project`、`run`、`secret_value`、`source`、`validation`、`worktree`。
- 未提供 `--object-type` 时，`--object-id` 必须是完整 ALab id，或稳定 audit literal `backups`、`cache`、`skydiscover` 之一。
- `--action` 使用 generic audit actions：`add`、`update`、`archive`、`unarchive`、`remove`、`restore`、`repair`、`revoke`、`regenerate`、`prune`、`gc`、`clear`。
- Success fields：`audit id`、`project id`、`exp id`、`actor type`、`actor credential id`、`action`、`object type`、`object id`、`cascade`、`reason`、`created at`。

`alab audit show <audit_id> [--project <project_id>]`

- Context：Any 或 Project。
- Credential：Root，或 event 所属 project 的 Root/admin。
- Audit output 使用 generic `action` 加 `object type`；`catalog_remove`、`worktree_remove`、`checkout_remove` 等 special action name 不是 V1 有效 output。
- Success fields：`audit id`、`project id`、`exp id`、`actor type`、`actor credential id`、`action`、`object type`、`object id`、`cascade`、`reason`、`deleted ids`、`sanitized metadata`、`created at`。
- `sanitized metadata` 不得包含 raw secret、token、verifier hash、hidden asset content 或 raw hidden log。

## 11. Source、Catalog、Experiment Commands

`alab source import ...`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Required args：`--source-path`、`--source-git`、`--source-empty` 三选一。
- Options：`--source-subdir`、`--name` 和 import limits；limit values 必须是 non-negative integers。
- Conflicts：多个 source origin；`--source-subdir` 与 `--source-empty`。
- Success fields：`project id`、`source id`、`source ref`、`source name`、`tree hash`、`deduped`、repeated `warning`。
- Exit：成功 `0`；source invalid、limit exceeded 或 name conflict 时 exit `2`；auth failure exit `3`。

`alab source list [--project <project_id>] [--include-archived]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields per source：`source id`、`source ref`、`source name`、`status`、`tree hash`、`created at`、`archived at`。
- Exit：成功 `0`；auth failure exit `3`。

`alab source show <source_id> [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields：`source id`、`source ref`、`source name`、`status`、`source commit`、`tree hash`、`origin type`、`origin summary`。
- Exit：成功 `0`；not found exit `2`；auth failure exit `3`。

`alab source archive|unarchive <source_id> [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Success fields for `archive`：`source id`、`previous status`、`source status`、`archived at`。
- Success fields for `unarchive`：`source id`、`previous status`、`source status`、`unarchived at`。
- Archive active default source 必须以 `RESOURCE_BUSY` exit `4` 失败。
- Exit：成功 `0`；auth failure exit `3`。

`alab source remove <source_id> [--project <project_id>] (--dry-run|--force --confirm <source_id>) [--cascade] [--reason <text>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Required args：`--dry-run`，或同时提供 `--force` 和匹配的 `--confirm`。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields：`source id`、`dry run`、`removed`、`cascade`、`audit id`、blocked 时 repeated `blocker`。
- Dry run 会渲染 blockers 和 deletion counts，但不写 audit rows，也不删除数据。
- Exit：成功 `0`；missing/wrong confirmation exit `2`；auth failure exit `3`；source 未 archived、任意 project config version 引用该 source，或 cascade blockers 存在时 exit `4`。

`alab catalog skydiscover add|update [--origin-url <url>] [--ref <ref>|--commit <sha>]`

- Context：Any。
- Credential：Root。
- Options：`--origin-url`；`--ref` 和 `--commit` 两者最多提供一个；`--commit` 要求 full commit SHA。
- Defaults：未提供 `--origin-url` 时使用 official SkyDiscover URL；未提供 `--ref` 或 `--commit` 时使用当前 upstream `main` 并 resolve/pin exact commit。
- `--ref` resolve 到 exact commit 后持久化；`--commit` 要求 full SHA 并验证存在。
- Success fields：`catalog`、`origin url`、`requested ref`、`pinned commit`、`local path`、`retrieved at`、`status`、`audit id`。
- Exit：成功 `0`；add 遇到 existing catalog、update 遇到 dirty catalog、invalid origin、invalid ref 或 invalid commit 时 exit `2`；auth failure exit `3`。

`alab catalog skydiscover show`

- Context：Any。
- Credential：Root。
- Success fields：`catalog`、`origin url`、`pinned commit`、`local path`、`retrieved at`、`status`。
- `show` 不得 fetch network。
- Exit：成功 `0`；没有 active catalog 时 exit `2`；auth failure exit `3`。

`alab catalog skydiscover remove --force --confirm skydiscover [--reason <text>]`

- Context：Any。
- Credential：Root。
- `remove` 需要 `--force --confirm skydiscover [--reason <text>]`，且 active config 或任何 open experiment bound config 引用 catalog 时失败。
- Success fields：`catalog`、`removed`、`audit id`。
- Exit：成功 `0`；missing/wrong confirmation exit `2`；active references exit `4`；auth failure exit `3`。

`alab cache prune [--docker-images] [--skydiscover-envs] [--trash --older-than <days>|--trash-all] [--all]`

- Context：Any。
- Credential：Root。
- Options：至少一个 cache selector。
- Conflicts：top-level `--all` 与 `--docker-images`、`--skydiscover-envs`、`--trash` 或 `--trash-all` 冲突。`--trash` 要求 `--older-than <days>`；`--trash-all` 删除全部 trash entries；top-level `--all` 包含 trash cleanup。
- Bounds：`--older-than` 必须大于等于 `0`。
- Success fields：`cache pruned count`、`cache kind`、`audit id`。

`alab exp create`

- Context：Project 或 explicit project。
- Credential：policy 允许时 Public，否则 Root/admin。
- Required args：`--name`；source origin 可省略并默认 project default source。
- Source conflicts：`--source-ref`、`--source-path`、`--source-git`、`--source-empty`、`--from-exp` 最多一个。
- Options：`--goal`、`--path`、repeated `--tag`、`--git-ref`、`--source-subdir`、`--from-commit latest|final|best|<sha>`、repeated `--mutable-include`、repeated `--mutable-exclude`、`--visibility-scope none|same_project|explicit`、repeated `--visible-exp`。
- `--from-commit` 仅在与 `--from-exp` 一起使用时有效；custom commit selector 必须是 full 或 unambiguous SHA-like commit id，不能是 arbitrary Git ref。
- Public no-key `--from-exp` 使用 public inheritance visibility：current project public policy 与 source experiment stored visibility upper bound 的交集。
- Public no-key `--from-exp` 允许从 visible open/closed experiment 继承，并支持 `final`、`latest`、`best` 和 source experiment branch 可达 SHA；archived source experiment 需要 Root/admin。
- Public no-key `--source-git` 可能使用 local non-interactive Git credential helper，并渲染 `PUBLIC_GIT_CREDENTIAL_HELPER_USED` warning；所有 prompt 都禁用。
- Experiment name slug conflict 始终以 `NAME_CONFLICT` 失败，不自动 suffix。
- Secret rule：create 写 raw worktree token 到 `token path`，但不打印 raw token。
- Success fields：`project id`、`exp id`、`experiment name`、`source id`、`branch`、`worktree path`、`token path`、`config version`、repeated `warning`、`next`。

`alab exp archive|unarchive <exp_id> [--project <project_id>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- Archive 是纯状态变更，不接受 worktree 删除参数。
- Success fields for `archive`：`exp id`、`previous status`、`experiment status`、`archived at`。
- Success fields for `unarchive`：`exp id`、`previous status`、`experiment status`、`unarchived at`。

`alab exp remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--cascade] [--reason <text>]`

- Context：Project 或 explicit project。
- Credential：Root/admin。
- `remove` 需要 experiment 已 archived，并需要 `--dry-run` 或 `--force --confirm <exp_id> [--cascade] [--reason <text>]`。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Cascade rule：experiment remove 是 whole-experiment deletion operation，因此 experiment 自身 archived 且不存在 active run/submit lock 后，child run、artifact、log、annotation、tag、inspection、worktree 和 submission records 不需要逐个 archived。
- Trash rule：actual remove 会在 DB/audit mutation 之前，把 registered worktree 和 inspection path，以及未被其他对象引用的 experiment log/artifact files stage 到 ALab trash。它会在 DB/audit mutation 前删除 experiment branch ref；如果 mutation 失败，则恢复该 ref。Experiment token rows 会被 revoke 并保留，path registry rows 会标记为 removed。
- Success fields：`exp id`、`dry run`、`removed`、`cascade`、`audit id`、repeated `blocker`、`deleted runs`、`deleted artifacts`、`deleted logs`、`deleted annotations`、`deleted tags`、`deleted submissions`、`branch ref`、dry-run `branch ref exists`、actual-run `deleted branch ref` 和 `branch ref existed`、`deleted filesystem paths`、dry-run repeated `filesystem path` 和 `planned trash move`、actual-run `trash cleanup pending`。

`alab exp checkout <exp_id> --path <dir> [--commit final|latest|best|<sha>]`

- Context：Project 或 explicit project。
- Credential：Root/admin 或 visible token。
- Options：`--commit latest|final|best|<sha>`；custom commit selector 必须是 full 或 unambiguous SHA-like commit id，不能是 arbitrary Git ref。
- Secret rule：checkout 写 raw inspection token 到 `token path`，但不打印 raw token。
- Success fields：`exp id`、`inspection path`、`inspection commit`、`token path`、`token id`、`next`。

`alab exp checkout remove (--token-id <token_id>|--path <dir>) [--project <project_id>] (--dry-run|--force --confirm <token_id-or-path-hash>) [--reason <text>]`

- Credential：Root/admin，或 matching inspection token 移除自己的 checkout。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- `--dry-run` 只报告将删除的 checkout path、token revocation target 和 planned trash move，不修改 DB、不写 audit、不删除文件。
- 实际删除 inspection worktree 时使用 ALab trash staging，revoke inspection token，并将 path registry 标记 removed；如果 staged trash 无法立即删除，后续由 `alab cache prune --trash --older-than <days>` 或 `alab cache prune --trash-all` 清理。
- Registered filesystem path 已经缺失时，actual remove 会调和 DB state、revoke inspection token、写 audit event，并 exit `0`。
- Success fields：`exp id`、`inspection path`、`token id`、`dry run`、`removed`、conditional `path exists` 或 `path existed`、`token revocation target`、`token revoked`、conditional `planned trash move` 或 `trash path`、conditional `trash cleanup pending`、`audit id`。

`alab exp worktree remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--reason <text>]`

- Credential：Root/admin。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- `--dry-run` 只报告 registered path、dirty state、token revocation target 和 planned trash move，不修改 DB、不写 audit、不删除文件。
- 实际删除 submit-capable worktree 时使用 ALab trash staging，设置 `worktree state: removed`，revoke active worktree token；如果 staged trash 无法立即删除，后续由 `alab cache prune --trash --older-than <days>` 或 `alab cache prune --trash-all` 清理。
- Registered filesystem path 已经缺失时，actual remove 会调和 DB state、revoke active worktree token、写 audit event，并 exit `0`。
- Success fields：`exp id`、`old worktree path`、`worktree state`、`dry run`、`removed`、conditional `path exists` 或 `path existed`、`dirty state`、`token revocation target`、`token revoked`、conditional `planned trash move` 或 `trash path`、conditional `trash cleanup pending`、`audit id`。

`alab exp worktree restore <exp_id> --path <dir> [--project <project_id>]`

- Credential：Root/admin。
- Checkout experiment branch HEAD，revoke old token，创建新 token，写入 `.alab/token`，并写 `.alab/` worktree-local Git exclude rule。
- Secret rule：restore 写 raw token 到 `token path`，但不打印 raw token。
- Success fields：`exp id`、`branch`、`worktree path`、`worktree state`、`token path`、`revoked token id`、`new token id`。

`alab exp token list|revoke|regenerate <exp_id> ... [--project <project_id>]`

- Credential：Root/admin。
- Selectors：`--token-id`、`--mode worktree|inspection`、`--all`。
- Conflicts：`--all` 与 `--token-id`/`--mode` 冲突。
- 默认 target 是 worktree token。
- Success fields per token for `list`：`project id`、`exp id`、`token id`、`token mode`、`status`、`path status`、`created at`、`revoked at`。
- Success fields for `revoke`：`project id`、`exp id`、`token id`、`token mode`、`status`、`revoked at`。
- Success fields for `regenerate`：`project id`、`exp id`、`revoked token id`、`new token id`、`token mode`、`token path`、`created at`。
- Secret rule：regenerate 写 registered path，不打印 raw token。

`alab exp tag add|remove|list`

- Credential：owning worktree token 或 Root/admin。
- Inspection token 不可变更 tag。
- Success fields for `add|remove|list`：`exp id`、`tag`、`action`、`tags`。

## 12. Run、Submit、Observe、Annotate

`alab run --message <message>`

- Context：Experiment。
- Credential：valid worktree token。
- Required args：`--message`。
- Success fields：`run id`、`exp id`、`commit`、`created commit`、`run status`、`exit code`、`reward`、`reward parse status`、`stdout preview`、`stderr preview`、`artifact count`、repeated `warning code`、`next`。
- `created commit` 渲染为 boolean。`stdout preview`、`stderr preview`、`artifact count` 和 repeated `warning code` 来自已保存的 run record，并与同一 run 的 observe output 保持一致。
- Auto commit rule：`run` 会 stage 所有 mutable-allowed 的 staged、unstaged、deleted、renamed、copied 和 untracked non-ignored changes，并创建一个 ALab auto commit；pre-existing staged set 不单独保留。
- Passed run exit `0`；saved failed/error/timeout run exit `1`。
- Manual commit 导致 full-diff mutable scope 失败时，ALab 记录 run `error`，返回 actionable `SCOPE_VIOLATION` details，并保持 HEAD/worktree 不变。

`alab submit --message <message> --summary <text>|--summary-file <path> --feedback <text>|--feedback-file <path> --ref <exp_id|none> [--ref <exp_id> ...] [--rerun]`

- Context：Experiment。
- Credential：valid worktree token。
- Summary/feedback direct text 与 file form 各自互斥。
- State rule：project must not be archived，experiment must be open，且 experiment worktree state must be active。
- Summary/feedback file 相对当前 command cwd 解析。
- Conflicts：`--ref none` 与任何 experiment ref 互斥。
- Refs 按 first-seen order 去重。
- Reuse rule：未提供 `--rerun` 时，`submit` 只复用 current HEAD 且 bound config version 相同的最近 passed run；没有可复用 run 时以 result failure 退出并提示 `--rerun`。
- Success fields：`exp id`、`submit accepted`、`final run id`、`final commit`、`experiment status`、`summary stored`、`feedback stored`、repeated `ref`。

`alab observe experiments list|search|show|best ...`

- Context：Project、Experiment 或 Inspection。
- Credential：Project context 用 Root/admin；Experiment/Inspection context 用 token visibility。
- Required args：`search --query`、`show <exp_id>`。
- Success fields per experiment：`project id`、`exp id`、`experiment name`、`experiment status`、`source id`、`source ref`、repeated `tag`、`latest run id`、`latest commit`、`final run id`、`final commit`、`best run id`、`reward`、`reward parse status`、`created at`、`updated at`、`closed at`、`archived at`。
- `best` warning fields：当 incompatible reward-policy runs 被排除时，渲染 `object: warning` block，包含 `warning code: BEST_INCOMPARABLE_RUNS_EXCLUDED`、稳定 `warning reason` 和 `excluded count`。

`alab observe runs list|show|archive|unarchive|remove ...`

- Context 和 credential：同 observe experiments。
- Required args：`show <run_id>`、`archive <run_id>`、`unarchive <run_id>`，或 `remove <run_id> (--dry-run|--force --confirm <run_id>)`。
- List filters：见 [spec_observe_collaboration.md](spec_observe_collaboration.md)。
- Options：`remove` 接受 `--cascade`、`--reason` 和 `--dry-run`。
- Conflicts：remove `--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields for `list|show`：`run id`、`exp id`、`commit`、`run status`、`exit code`、`reward`、`reward parse status`、`config version`、`stdout preview`、`stderr preview`、`artifact count`、`log count`、`hidden log available`、`started at`、`ended at`、repeated `warning code`。
- Success fields for `archive`：`run id`、`previous archive status`、`archive status`、`archived at`、`audit id`。
- Success fields for `unarchive`：`run id`、`previous archive status`、`archive status`、`unarchived at`、`audit id`。
- Success fields for `remove`：`run id`、`dry run`、`removed`、`cascade`、`audit id`、repeated `blocker`、`deleted artifacts`、`deleted logs`、`active dependent artifacts`、`active dependent logs`、`latest run id before`、`latest run id after`、`final run removed`、`deleted filesystem paths`、dry-run repeated `filesystem path` 和 `planned trash move`，以及 actual-run `trash cleanup pending`。
- Credential：owning worktree token 可 archive/unarchive 自己 experiment 的 runs；remove 需要 Root/admin。
- Remove cascade rule：带 dependent artifact 或 log row 的 archived run 在未传 `--cascade` 时输出 `dependent_records_require_cascade`；传入 `--cascade` 后，active dependent artifact/log row 会输出 `dependent_records_not_archived`；已 archived 的 dependent row 会在同一个 audited operation 中删除，未共享文件会在 DB mutation 前 stage 到 ALab trash。

`alab observe artifacts list|show|export|archive|unarchive|remove ...`

- Context 和 credential：同 observe experiments。
- Required args：`show <artifact_id>`、`export <artifact_id> --out <path>`、`archive <artifact_id>`、`unarchive <artifact_id>`，或 `remove <artifact_id> (--dry-run|--force --confirm <artifact_id>)`。
- List filters：见 [spec_observe_collaboration.md](spec_observe_collaboration.md)。
- Options：export 接受 `--overwrite` 和 `--include-archived`；remove 接受 `--cascade`、`--reason` 和 `--dry-run`。
- Conflicts：remove `--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields for `list|show|export`：`artifact id`、`exp id`、`run id`、`validation id`、`root`、`path`、`status`、`archive status`、`size bytes`、`content hash`、`created at`、`out`。
- Success fields for `archive`：`artifact id`、`previous archive status`、`archive status`、`archived at`、`audit id`。
- Success fields for `unarchive`：`artifact id`、`previous archive status`、`archive status`、`unarchived at`、`audit id`。
- Success fields for `remove`：`artifact id`、`dry run`、`removed`、`cascade`、`audit id`、repeated `blocker`、`deleted filesystem paths`、dry-run repeated `filesystem path` 和 `planned trash move`，以及 actual-run `trash cleanup pending`。
- Artifact/log export 在 target exists 且没有 `--overwrite` 时以 `OUTPUT_EXISTS` 失败。
- Archived artifacts 可在授权后按 id show。Export archived artifacts 需要 `--include-archived`。
- Credential：owning worktree token 可 archive/unarchive own experiment artifacts；remove 需要 Root/admin。
- Remove filesystem rule：captured artifact blob 只有在没有 remaining artifact row 引用同一 blob path 时才会 stage 到 ALab trash。

`alab observe logs list|show|export|archive|unarchive|remove ...`

- Context 和 credential：同 observe experiments；hidden logs 需要 Root/admin 且显式 `--include-hidden`。
- Required args：`show <log_id>`、`export <log_id> --out <path>`、`archive <log_id>`、`unarchive <log_id>`，或 `remove <log_id> (--dry-run|--force --confirm <log_id>)`。
- List filters：见 [spec_observe_collaboration.md](spec_observe_collaboration.md)。
- Options：show/export 接受 `--include-hidden`；export 接受 `--include-archived`；remove 接受 `--cascade`、`--reason` 和 `--dry-run`。
- Conflicts：remove `--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields for `list|export`：`log id`、`exp id`、`run id`、`validation id`、`stream`、`size bytes`、`stored bytes`、`truncated`、`hidden`、`archive status`、`preview`、`out`、`audit id`。
- Success fields for `show`：`log id`、`exp id`、`run id`、`validation id`、`stream`、`size bytes`、`stored bytes`、`truncated`、`hidden`、`archive status`、`preview`、`content`、`out`、`audit id`。
- Success fields for `archive`：`log id`、`previous archive status`、`archive status`、`archived at`、`audit id`。
- Success fields for `unarchive`：`log id`、`previous archive status`、`archive status`、`unarchived at`、`audit id`。
- Success fields for `remove`：`log id`、`dry run`、`removed`、`cascade`、`audit id`、repeated `blocker`、`deleted filesystem paths`、dry-run repeated `filesystem path` 和 `planned trash move`，以及 actual-run `trash cleanup pending`。
- Archived logs 可在授权后按 id show，包括 log text。Export archived logs 需要 `--include-archived`。
- Credential：owning worktree token 可 archive/unarchive own visible logs；hidden log lifecycle 和 remove 需要 Root/admin。
- Remove filesystem rule：log file 只有在没有 remaining log row 引用同一 file path 时才会 stage 到 ALab trash。

`alab observe annotations list|show ...`

- Context 和 credential：同 observe experiments。
- Required args：`show <annotation_id>`。
- List filters：见 [spec_observe_collaboration.md](spec_observe_collaboration.md)。
- Options：`--history`。
- Success fields per annotation：`annotation id`、`target type`、`target id`、`resolved commit`、`status`、`current revision`、`visibility`、`author`、`body`、`created at`、`updated at`、repeated `revision`。

`alab annotate add --target <target> --body <text>|--body-file <path> [--author <label>] [--private] [--private-to-exp <exp_id>]`

- Context：Experiment 或 Project。
- Credential：visible token/creating token，或 Root/admin。
- Required args：target 和 exactly one body input。
- Conflicts：`--body` 与 `--body-file` 互斥；token context 与 `--private-to-exp` 互斥。
- Project-context add/edit 在 target annotation 不能精确 resolve 到一个 experiment 时，必须在 body storage 前以 `CONFIG_INVALID` 失败。
- Success fields：`annotation id`、`target type`、`target id`、`resolved commit`、`revision`、`visibility`、`created at`。

`alab annotate edit <annotation_id> --body <text>|--body-file <path> [--author <label>]`

- Context：Experiment 或 Project。
- Credential：creating token for its annotation，或 Root/admin。
- Required args：annotation id 和 exactly one body input。
- Success fields：`annotation id`、`revision`、`updated at`。

`alab annotate archive <annotation_id>`

- Context：Experiment 或 Project。
- Credential：creating token for its annotation，或 Root/admin。
- Success fields：`annotation id`、`previous status`、`annotation status`、`archived at`。

`alab annotate unarchive <annotation_id>`

- Context：Experiment 或 Project。
- Credential：creating token for its annotation，或 Root/admin。
- Success fields：`annotation id`、`previous status`、`annotation status`、`unarchived at`。

`alab annotate remove <annotation_id> (--dry-run|--force --confirm <annotation_id>) [--reason <text>]`

- Context：Experiment 或 Project。
- Credential：creating token for its annotation，或 Root/admin。
- `remove` 需要 annotation 已 archived，并需要 `--dry-run` 或 `--force --confirm <annotation_id> [--reason <text>]`。
- Conflicts：`--dry-run` 不能与 `--force` 或 `--confirm` 混用。
- Success fields：`annotation id`、`dry run`、`removed`、`audit id`、repeated `blocker`、`deleted revisions`、`deleted filesystem paths`，以及 actual-run `trash cleanup pending`。
