# ALab V1 Observe 和 Collaboration 规格

本文档是 [spec_observe_collaboration.md](spec_observe_collaboration.md) 的中文同步版。英文版是规范性来源。

## 1. Visibility Model

Project visibility config：

```toml
[visibility]
scope = "same_project" # none|same_project|explicit
experiment_ids = []
```

Effective visibility：

- Current project policy 在 authorization time 评估。
- Experiment policy 在 experiment creation time 存储，并作为 per-experiment upper bound。
- Effective token visibility 是 current project policy 与 source experiment stored experiment policy 的交集。
- 后续 project policy change 可以在 experiment policy bound 内收窄或扩展 existing token authorization。
- 后续 project policy change 不能授予 source experiment stored experiment policy 外的访问。
- Regenerated token 使用同一 visibility formula，不重写 experiment policy。
- Tags 不影响 authorization。
- Experiment 或 inspection token 始终可 inspect 自己的 experiment records。Visibility scope 只控制对其他 experiments 的访问。
- Project context 中 root/admin 可 inspect 和 maintain 所有 project records。
- Experiment token 只能 inspect effective visible records。
- Inspection token 使用同一 effective visibility formula，且不能 mutation。
- Archived experiments 默认从 list/search/best 隐藏，但 archive state 不是 authorization policy field。

Visibility selector：

- `none`：不可见其他 experiment records。
- `same_project`：同 project records 可见。
- `explicit`：仅列出的 experiment ids 可见。

Public access：

- Public no-key experiment creation 默认启用。
- Public no-key checkout 不允许。
- Public no-key observe history 不允许。
- Public no-key `exp create --from-exp` 使用 public inheritance visibility，而不是 token visibility。Public inheritance visibility 是从 public project context 评估的当前 project visibility policy 与 source experiment stored visibility upper bound 的交集。交集后，`none` 不允许任何 experiment source，`same_project` 允许 project 内 open/closed experiment，`explicit` 只允许列出的 open/closed experiment id。没有 raw experiment token 参与，但 source experiment stored upper bound 仍然限制 public inheritance。这是 source-inheritance operation，不是 observe command。
- No-key project status 只能输出 safe project summary。
- Public project 的历史查看必须通过带有效 token 的 experiment worktree 或 inspection checkout。

## 2. Observe Commands

Primary commands：

```text
alab observe experiments list [filters]
alab observe experiments search --query <text> [filters]
alab observe experiments show <exp_id>
alab observe experiments best [filters]
alab observe runs list [filters]
alab observe runs show <run_id>
alab observe runs archive <run_id>
alab observe runs unarchive <run_id>
alab observe runs remove <run_id> (--dry-run|--force --confirm <run_id>) [--cascade] [--reason <text>]
alab observe artifacts list [filters]
alab observe artifacts show <artifact_id>
alab observe artifacts export <artifact_id> --out <path> [--overwrite] [--include-archived]
alab observe artifacts archive <artifact_id>
alab observe artifacts unarchive <artifact_id>
alab observe artifacts remove <artifact_id> (--dry-run|--force --confirm <artifact_id>) [--cascade] [--reason <text>]
alab observe logs list [filters]
alab observe logs show <log_id> [--include-hidden]
alab observe logs export <log_id> --out <path> [--overwrite] [--include-hidden] [--include-archived]
alab observe logs archive <log_id>
alab observe logs unarchive <log_id>
alab observe logs remove <log_id> (--dry-run|--force --confirm <log_id>) [--cascade] [--reason <text>]
alab observe annotations list [filters]
alab observe annotations show <annotation_id> [--history]
```

Aliases：

```text
alab exp list|search|show|best
alab runs list|show|archive|unarchive|remove
alab artifacts list|show|export|archive|unarchive|remove
alab logs list|show|export|archive|unarchive|remove
alab annotations list|show
```

Context behavior：

- Project context 需要 root/admin key，可 inspect all project records。
- Experiment context 使用 token visibility。
- Inspection context 使用 inspection token visibility。
- Archived records 默认从 list/search/best 隐藏，但 authorized 时可按 id show。
- Archived artifact/log export 仍要求显式 `--include-archived`。

## 3. Search、Pagination、Sorting

Search：

- V1 使用 plaintext local records，在 process 内扫描 SQLite/file-backed records。
- `--query` 是 case-insensitive substring matching。
- Search corpus 包括 caller 可见的 project/experiment names/goals、task text、tags、final summaries、feedback、latest annotation titles 和 latest annotation bodies。
- V1 search 不扫描 run stdout/stderr logs、hidden logs、artifact bytes、historical annotation revisions。

Pagination：

- `list`、`search`、`best` 支持 `--limit <n>` 和 `--offset <n>`。
- 默认 `--limit` 为 `50`。
- `--limit` 必须在 `1` 到 `500` 之间。
- `--offset` 必须大于等于 `0`。

Sorting：

- 除非命令显式收窄 surface，否则支持 `--sort <field>:<asc|desc>`。
- Sort fields 是 command-specific whitelist。
- Unknown sort field 以 `CONFIG_INVALID` 失败。
- List/search 默认按最相关 timestamp descending；best 默认按 reward ranking。
- Experiment list/search sort fields：`created`、`updated`、`name`、`status`、`reward`。
- Experiment best 不接受 `--sort`；它始终使用 reward-policy ranking。
- Run list sort fields：`started`、`ended`、`reward`、`status`、`config-version`、`exit-code`。
- Artifact list sort fields：`created`、`path`、`size`、`status`、`content-hash`。
- Log list sort fields：`created`、`stream`、`size`、`stored-bytes`、`hidden`、`truncated`。
- Annotation list sort fields：`created`、`updated`、`title`、`target-type`、`target-id`、`status`、`created-by`。
- Sort value 为 nullable 的 rows 始终排在有具体值的 rows 之后。

## 4. Filters

Experiment list/search/best filters：

- `--status` 接受 `open`、`closed` 或 `archived`
- repeated `--tag`
- `--source-id`
- `--name-query`
- `--reward-min`
- `--reward-max`
- 同时提供 reward bounds 时，`--reward-min` 必须小于或等于 `--reward-max`。
- `--config-version` 接受正整数 config version number
- `--created-after`
- `--created-before`
- `--updated-after`
- `--updated-before`
- `--include-archived`

同一字段 family 中 matching `after` 和 `before` time bounds 必须有序。
Repeated `--tag` 使用 AND semantics。

Run list filters：

- `--exp`
- `--status`
- `--config-version` 接受正整数 config version number
- `--commit` 接受完整或缩写的十六进制 commit SHA prefix
- `--reward-min`
- `--reward-max`
- 同时提供 reward bounds 时，`--reward-min` 必须小于或等于 `--reward-max`。
- `--runner-type` 接受 `local`、`docker`、`harbor`、`skydiscover_docker` 或 `skydiscover_python`
- `--exit-code`
- `--failure-reason-query`
- `--started-after`
- `--started-before`
- `--ended-after`
- `--ended-before`
- `--include-archived`

同一字段 family 中 matching `after` 和 `before` time bounds 必须有序。

Artifact list filters：

- `--exp`
- `--run`
- `--validation`
- `--root` 接受 `workspace` 或 `run`
- `--status`
- `--path-query`
- `--content-hash` 接受 `sha256:<64-hex>`
- `--created-after`
- `--created-before`
- `--size-min` 接受 non-negative integer byte count
- `--size-max` 接受 non-negative integer byte count
- 同时提供 size bounds 时，`--size-min` 必须小于或等于 `--size-max`。
- `--include-archived`

同一字段 family 中 matching `after` 和 `before` time bounds 必须有序。

Log list filters：

- `--exp`
- `--run`
- `--validation`
- `--stream` 接受 `stdout`、`stderr`、`hidden_stdout` 或 `hidden_stderr`
- `--truncated`
- `--created-after`
- `--created-before`
- `--include-hidden`
- `--include-archived`

同一字段 family 中 matching `after` 和 `before` time bounds 必须有序。

Annotation list filters：

- `--target-type`
- `--target-id`
- `--author`
- `--created-by`
- `--private`
- `--query`
- `--created-after`
- `--created-before`
- `--updated-after`
- `--updated-before`
- `--include-archived`
- Object-backed `--target-id`/`--target` values 在 target type 已选择或可推断时必须是完整 experiment、run 或 artifact ids。`--created-by` 必须是完整 experiment 或 credential id。

同一字段 family 中 matching `after` 和 `before` time bounds 必须有序。

## 5. Best Ranking

规则：

- 每个 visible experiment 最多贡献一个 qualifying run。
- Qualifying run 必须有 parsed numeric reward。
- Free evaluation submissions 使用 `final_run_id = NULL`，不会创建 run 或 reward rows，也永远不会进入 best ranking。
- 默认排除 failed、error、timeout、running、interrupted runs。
- 默认排除 archived runs。
- Ranking 使用 comparable reward policy set 的 reward direction。
- 默认情况下，`best` 只比较 bound reward policy identity 与当前 active project reward policy 相同的 runs。Reward policy identity 包括 reward type、direction、primary metric，以及会影响 numeric value 的 reward extractor fields。
- Reward policy identity comparison 独立于 config version。不同 config versions 的 runs 只有在 reward policy identity 匹配时才能一起排名。
- 如果 project 当前 invalid，默认 `best` 仍使用 active valid config 的 reward policy identity。如果 project 没有 active valid config，`best` 以 `PROJECT_INVALID` 失败，并要求显式 `--config-version`。
- 提供 `--config-version <n>` 时，`<n>` 必须为正整数，`best` 只比较绑定该 config version 的 visible runs。
- Incompatible reward policy identity 的 runs 会被排除。`best` 会把 `BEST_INCOMPARABLE_RUNS_EXCLUDED` 渲染为 warning block，并带 excluded count。
- Tie 先按 run ended time descending，再按 experiment id。

## 6. Runs Show 和 Logs

`observe runs show`：

- 输出 fixed-size stdout/stderr previews。
- 输出 full log access 所需 log ids。
- 输出 log sizes、stored byte counts、truncation flags，以及 admin/root 可见的 hidden log availability boolean。
- 不输出 full logs。
- 不输出 hidden log contents。

`observe logs list|show|export`：

- Visible logs 按 visibility 对 authorized token 可用。
- Hidden logs 需要 root/admin 且显式 `--include-hidden`。
- Token-only context 中 `--include-hidden` 被拒绝。
- Archived logs 默认从 list 隐藏。
- 按 id show archived log，包括 log text，需要 authorization，但不要求 `--include-archived`。
- Export archived log 要求 `--include-archived`。
- `logs show` 从 stored bytes 渲染 safe decoded text，并遵守 output size limits。
- `logs export` 写 exact stored bytes。
- Export target exists 且未提供 `--overwrite` 时，以 `OUTPUT_EXISTS` 失败。
- Export parent directory 必须存在；ALab 不会为 log export 创建缺失的 parent directory。

Hidden logs：

- 包括 Harbor verifier raw stdout/stderr 和 SkyDiscover evaluator raw stdout/stderr。
- Hidden logs 是 file-backed，并由 SQLite index。
- Hidden logs 不是 artifacts。
- Token-visible commands 只能显示不会泄露 hidden asset contents 的 safe hidden-log summaries。

## 7. Artifact Export

Commands：

```text
alab observe artifacts show <artifact_id>
alab observe artifacts export <artifact_id> --out <path> [--overwrite] [--include-archived]
```

规则：

- 默认 output path exists 时以 `OUTPUT_EXISTS` 失败。
- `--overwrite` 替换 existing files。
- Archived artifacts 可在 authorized 时按 id show。Export archived artifact 要求 `--include-archived`。
- Parent directory 必须存在。
- Export 写 exact captured bytes。
- Artifact export 不 redact artifact bytes 中的 `secret_env` values。
- Hidden assets 绝不是 valid artifacts，不能通过该命令 export。

## 8. Tags

Commands：

```text
alab exp tag add <exp_id> <tag> [--project <project_id>]
alab exp tag remove <exp_id> <tag> [--project <project_id>]
alab exp tag list <exp_id> [--project <project_id>]
```

Permissions：

- Experiment token 可管理 own experiment tags。
- Root/admin 可管理 project 内任意 experiment tags。
- Inspection tokens 不可管理 tags。

规则：

- Tags 是 metadata，永不授予 visibility。
- Tags normalize 为 lowercase slug form。
- Tags 在 lowercase ASCII slug normalization 后最长 64 bytes。
- Duplicate normalized tags 不创建重复项，并输出稳定结果。

## 9. Annotation Commands

Commands：

```text
alab annotate add [--target <target>] [--exp <exp_id>] [--title <title>] --body <text>|--body-file <path> [--author <label>] [--private] [--private-to-exp <exp_id>]
alab annotate edit <annotation_id> --body <text>|--body-file <path> [--author <label>]
alab annotate archive <annotation_id>
alab annotate unarchive <annotation_id>
alab annotate remove <annotation_id> (--dry-run|--force --confirm <annotation_id>) [--reason <text>]
alab observe annotations list [filters]
alab observe annotations show <annotation_id> [--history]
```

Targets：

```text
exp:<exp_id>
run:<run_id>
artifact:<artifact_id>
path:<exp_id>@<commitish>:<repo_path>
lines:<exp_id>@<commitish>:<repo_path>:<start>-<end>
path:<repo_path>
lines:<repo_path>:<start>-<end>
```

Targetless notes：

- 省略 `--target` 会创建 targetless annotation，并绑定到一个 concrete experiment id。
- 在 experiment worktree 中，targetless annotation 绑定当前 experiment。
- 在 root/admin project context 中创建 targetless annotation 时必须提供 `--exp <exp_id>`。
- Targetless annotations 必须提供 `--title`；targeted annotations 也可以提供 `--title`。
- Stored targetless annotations 使用 `target_type = none`、empty `target_id`，并在 `annotations.target_json` 中保存 bound experiment id。

Commitish：

- 支持 common aliases `HEAD`、`head`、`latest`、`final`、`best`。
- 支持 full 或 unambiguous commit SHA。
- Root/admin 从 project context 调用时可支持 registered ALab branch names。
- Annotation creation 时 resolve 为一个 concrete commit SHA。
- Stored annotation 不把 moving alias 作为 authoritative target。
- Stored annotations 在 `annotations.target_json` 中保存 normalized target details，使 line range、repo path、resolved experiment id 和 resolved commit 不依赖重新解析 display string。

Path 和 line rules：

- Path/line targets 必须使用 normalized forward-slash repo-relative paths，不能包含 absolute、Windows-absolute、empty、`.`、`..`、backslash、NUL 或 newline components。
- Line range 必须是 positive integer 1-based inclusive range，且 `end >= start`。
- File/line targets anchored 到 experiment 和 resolved commit。
- `path:` target 要求 target path 在 resolved commit 存在，且是 Git blob 或 tree。
- `lines:` target 要求 target path 在 resolved commit 存在且是 Git blob，并且 inclusive line range 对 captured file contents 有效。
- Current experiment shorthand 只允许在 experiment context 中使用，并在 annotation creation 时 resolve 到当前 experiment current HEAD commit。
- Current experiment shorthand 要求 worktree clean。如果存在 staged、unstaged、deleted、renamed、copied 或 untracked non-ignored changes，annotation creation 失败，不会锚定未提交内容。

Visibility：

- Annotation 可 target visible records。
- Targetless annotations 按其 bound experiment 和 annotation visibility 判断可见性。
- Annotation 默认 project visibility。
- Annotation visibility 绝不会扩大 target visibility。Caller 只有在 normal visibility rules 下也能看到 target record 时，才能看到 project-visible annotation。
- `--private` 限制为 creating experiment 和 root/admin 可见，即使 target 属于另一个 visible experiment。
- Experiment-private annotation 绑定 creating experiment identity，而不是某一个 raw token value。同一 experiment 的 regenerated worktree token 可在 normal creating-experiment ownership rules 下查看和编辑该 experiment 的 private annotations。
- Project context 中 root/admin 必须用 `--private-to-exp <exp_id>` 创建 experiment-private annotation。
- Annotation target object ids 与 `--private-to-exp` experiment ids 必须在 body-file reads 或 body storage 前校验为完整 ALab ids。
- Private annotation 即使 project visibility 后续变宽，也保持 private。
- Inspection tokens 不可 add/edit annotations。
- Validation-owned artifact rows 不携带 experiment id，因此作为 annotation target 会以 `CONFIG_INVALID` rejected；annotation 需要绑定到具体 experiment 时，应使用 experiment/path/line target 或 run-owned artifact target。

Title 和 body input：

- Annotation body 是 UTF-8 text。
- Annotation title 是 UTF-8 text，storage 前 trim；提供时不得为空，编码后最多 256 bytes。
- 编码后最多 65536 bytes。
- Body input 只接受 direct text 或 file input 二选一。
- V1 不支持 `--body-stdin`。
- Targetless annotation creation 在缺少 `--title` 或 title 为空白时以 `CONFIG_INVALID` 失败。
- `--target ""` 非法；targetless annotations 必须完全省略 `--target`。
- Annotation body 不得包含 authoring experiment bound config version 下 active `secret_env` values 的 exact match。发现 exact secret value 时，creation/edit fail，且不存 revision。
- Annotation title 不得包含 authoring experiment bound config version 下 active `secret_env` values 的 exact match。
- Root/admin 从 project context 创建或编辑 annotation 时，authoring secret check 使用 target experiment 的 bound config version。无法 resolve 到唯一 experiment 的 target 在 body storage 前以 `CONFIG_INVALID` rejected，必须改写为带有 concrete experiment identity 的 target；需要 experiment-private visibility 时，root/admin 再使用 `--private-to-exp <exp_id>`。

Revision 和 archive：

- Annotation edit 创建 revision。
- Creator experiment token 可 edit 自己创建的 annotation。
- 同一 experiment 的 regenerated worktree token 在 experiment-private annotation visibility 和 edit 权限上视为 creator experiment token。旧 token 被 revoked 后，只要存在新的 active worktree token，该 experiment 的 private annotations 不会变成 root/admin-only。
- Root/admin 可 edit project 内任意 annotation。
- Edit 不可改变 target。
- `annotate archive` 使用与 edit 相同的 authorization rules。
- `annotate unarchive` 使用与 archive 相同的 authorization rules。
- `annotate remove` 使用与 archive 相同的 authorization rules，要求 annotation 已 archived，在同一个 audited transaction 中删除全部 revisions，记录 `deleted_revision_count`，且没有 filesystem target。
- Archive tombstone annotation，不删除 revisions。
- Archived annotations 默认从 list/search 隐藏，但 authorized 时可按 id show。

## 10. Public Safe Status

Public safe status 可包含：

- project id
- project name
- task
- goal
- project status
- default source id/name/content hash
- mutable summary
- visibility summary
- runner type，包括 free evaluation projects 的 `none`
- timeout
- working directory
- reward type，包括 free evaluation projects 的 `none`
- reward direction
- primary metric
- artifact/log limits
- next action

Public safe status 不得包含：

- project history
- experiment records
- run records
- artifacts
- annotations
- `env` values
- `secret_env` names or values
- full runner command
- generated verifier/evaluator commands
- hidden assets
- raw hidden logs
- absolute catalog paths
- adapter staging paths
- baseline failure logs

如果 project invalid，no-key public status 只输出 invalid status 和 admin next action。
