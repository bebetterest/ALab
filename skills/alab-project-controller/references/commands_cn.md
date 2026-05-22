# ALab Project Controller Commands

## 推荐的 Admin Invocation

通过 stdin 传递 project admin key：

```sh
printf '%s\n' "$ALAB_PROJECT_KEY" | alab --key-stdin project show --project "$ALAB_PROJECT_ID"
```

环境变量中有 secrets 时不要打开 shell tracing。不要把 raw keys 写入 prompts、run messages、summaries 或 reports。

## Project-Scoped Surface

Project controller 可以使用 same-project admin commands：

```text
alab project show|archive|unarchive ...
alab status --project <project_id>
alab project config show|export|import|set ...
alab project env set|unset|list ...
alab project secret set|unset|list|gc ...
alab project validate ...
alab project validation archive|unarchive|remove ...
alab source import|list|show|archive|unarchive|remove ...
alab exp create|list|search|show|best|archive|unarchive|remove ...
alab exp checkout ...
alab exp checkout remove ...
alab exp worktree remove|restore ...
alab exp token list|revoke|regenerate ...
alab exp tag add|remove|list ...
alab observe experiments|runs|artifacts|logs|annotations ...
alab annotate add|edit|archive|unarchive|remove ...
alab audit list|show --project <project_id> ...
```

## 功能明细

每项说明功能、作用、关键参数和输出/注意点。

- **`project show`**：查看单个 project summary。
  关键参数：不在 project context 中时使用可选 `--project <project_id>`。
  注意点：用于确认 project id、status、task、goal、active config version、default source、runner、reward、visibility 和 public experiment policy。
- **`status`**：获取安全的当前状态 summary。
  关键参数：可选 `--project <project_id>`。
  注意点：创建 workers 前或 context marker 不明确时很有用。
- **`project config show`**：查看 retained config metadata。
  关键参数：可选 `--project`；`--version latest-attempted|active-valid|<n>`。
  注意点：显示 runner/reward/artifact/env/secret fingerprints，但不显示 raw secret values。
- **`project config export`**：将 config snapshot 写入文件。
  关键参数：必需 `--out <path>`；可选 `--overwrite`、`--project`、`--version`。
  注意点：用于 review 或受控编辑；export 永不写出 raw secret values。
- **`project config import`**：导入 config file，并按需运行 baseline validation。
  关键参数：必需 `--config <path>`；可选 `--project`、`--dry-run`、`--skip-baseline-test`；`--dry-run` 与 skip 冲突。
  注意点：Dry-run 会 parse、canonicalize、diff 并检查 capabilities，不写 DB/file，也不执行 runner。
- **`project config set`**：修改一个 non-secret config field。
  关键参数：必需 `<field> <toml-literal>`；可选 `--project`、`--dry-run`、`--skip-baseline-test`。
  注意点：Array/map 字段整体替换；secret fields 必须用 `project secret`。
- **`project env set|unset|list`**：管理 project config 中的 plain environment values。
  关键参数：`set <name> <value>`、`unset <name>` 或 `list`；可选 `--project`。名称必须符合 environment-variable 语法。
  注意点：`list` 会渲染 values；敏感值应使用 secrets。
- **`project secret set|unset|list|gc`**：管理 secret environment values 和 unreferenced secret bytes。
  关键参数：`set <name> --value-stdin|--value-file <path>`、`unset <name>`、`list` 或 `gc --dry-run|--apply`；可选 `--project`。
  注意点：Raw secret values 永不渲染；输入必须是非空 single-line UTF-8，且无 NUL bytes。
- **`project validate`**：运行 active project baseline validation。
  关键参数：可选 `--project <project_id>`。
  注意点：输出 validation id、status、reward、parse status、warning codes 和 project status。
- **`project validation archive|unarchive|remove`**：维护 validation records 及其 dependent logs/artifacts。
  关键参数：必需 `<validation_id>`；remove 需要 `--dry-run` 或 `--force --confirm <validation_id>`，可选 `--cascade`、`--reason`、`--project`。
  注意点：Active validation 不能 archive；remove 前先 dry-run。
- **`project locks clear-stale`**：清理 stale project locks。
  关键参数：可选 `--project <project_id>`。
  注意点：只用于 stale locks；输出 cleared lock names 和 audit id。
- **`source import`**：添加 reusable source snapshot。
  关键参数：`--source-path`、`--source-git`、`--source-empty` 三选一；可选 `--source-subdir`、`--name`、source size limits、`--project`。
  注意点：Imports 会生成 canonical source refs；source limits 必须是非负数。
- **`source list|show`**：查看 retained sources。
  关键参数：`show` 需要 `<source_id>`；list 可选 `--project`、`--include-archived`。
  注意点：用于选择新 experiments 的 source refs，并验证 origin summaries。
- **`source archive|unarchive|remove`**：维护 project sources。
  关键参数：必需 `<source_id>`；remove 需要 `--dry-run` 或 `--force --confirm <source_id>`，可选 `--cascade`、`--reason`、`--project`。
  注意点：Active/default 或 referenced sources 可能阻止 archive/remove。
- **`exp create`**：创建新的 experiment worktree 和 token。
  关键参数：必需 `--name`；可选 `--project`、`--goal`、`--path`、重复 `--tag`、`--source-ref`、`--source-path`、`--source-git`、`--source-empty`、`--from-exp`、`--from-commit latest|final|best|<sha>`、mutable include/exclude、visibility options。
  注意点：最多一个 source origin。Raw worktree token 写入 token path，永不打印。
- **`exp list|search|show|best`**：查看并排序 project experiments。
  关键参数：Search 需要 `--query`；filters 包括 status、tags、source id、name query、reward bounds、config version、timestamps、archive flag、pagination，以及支持处的 sorting。
  注意点：用于选择 predecessors、refs 和 worker targets。
- **`exp archive|unarchive|remove`**：维护 experiment lifecycle。
  关键参数：必需 `<exp_id>`；remove 需要 `--dry-run` 或 `--force --confirm <exp_id>`，可选 `--cascade`、`--reason`、`--project`。
  注意点：Remove 是 archive-first，可能把 worktrees、inspection paths、logs、artifacts 和 branch refs stage 到 trash。
- **`exp checkout`**：为可见 experiment commit 创建 inspection checkout。
  关键参数：必需 `<exp_id> --path <dir>`；可选 `--commit final|latest|best|<sha>`、`--project`。
  注意点：会把 inspection token 写到 token path，永不打印。
- **`exp checkout remove`**：移除 inspection checkout。
  关键参数：`--token-id` 或 `--path` 二选一；再加 `--dry-run` 或 `--force --confirm <token_id-or-path-hash>`；可选 `--project`、`--reason`。
  注意点：可 reconcile 已缺失路径；使用 trash staging。
- **`exp worktree remove|restore`**：移除或恢复 submit-capable worktrees。
  关键参数：Remove 需要 `<exp_id>` 加 `--dry-run` 或 `--force --confirm <exp_id>`；restore 需要 `<exp_id> --path <dir>`；可选 `--project`。
  注意点：Remove revoke active worktree token；restore 写 replacement token，永不打印。
- **`exp token list|revoke|regenerate`**：查看或替换 experiment tokens。
  关键参数：必需 `<exp_id>`；selectors 为 `--token-id`、`--mode worktree|inspection` 或 `--all`。
  注意点：Regenerate 会把 raw token 写到 registered path，永不打印。
- **`exp tag add|remove|list`**：管理 experiment labels。
  关键参数：必需 `<exp_id>`；add/remove 还需要 tag text。
  注意点：用于 search、worker 分组和比较相关 attempts。
- **`observe experiments|runs|artifacts|logs|annotations`**：读取或维护 project-visible evidence。
  关键参数：使用对应 observe filters：experiment/runs/artifacts/logs/annotations list filters、`show <id>`、export `--out`、archive/unarchive，以及 admin-only remove dry-run/confirm。
  注意点：Hidden logs 需要 root/admin 和显式 `--include-hidden`；observe outputs 是决策证据。
- **`annotate add|edit|archive|unarchive|remove`**：添加或维护 project notes。
  关键参数：`add` 需要 `--target` 和一个 body input；可选 `--author`、`--private`、`--private-to-exp`；edit 需要 annotation id 和 body；remove 需要 dry-run 或 force/confirm。
  注意点：用于 decision records、review notes 和 project-visible guidance。
- **`audit list|show --project`**：查看 project-scoped audit evidence。
  关键参数：Filters 包括 `--object-type`、`--object-id`、`--action`、`--actor`、time bounds、`--limit`、`--offset`；show 需要 `<audit_id>`。
  注意点：用于验证 lifecycle、credential、config、source、validation 和 cleanup actions。

谨慎使用 remove commands：

- 先运行 `--dry-run`。
- 只有理解 blocker list 后，才使用精确的 `--force --confirm <id>`。
- 如果 command 要求 archive-first deletion，先 archive target，再 hard remove。

## 禁止的 Global Surface

Project controller 不应运行 root-only commands：

```text
alab auth init
alab auth root regenerate
alab key create
alab key list --root
alab key revoke
alab project init
alab project remove
alab catalog skydiscover add|update|remove
alab cache prune
alab backup prune
```

当 admin key 允许时，`alab key list --project <project_id>` 可用于 same-project inspection。创建或 revoke admin key 属于 global-admin task。

## Experiment Creation Patterns

Default source：

```sh
printf '%s\n' "$ALAB_PROJECT_KEY" | alab --key-stdin exp create \
  --project "$ALAB_PROJECT_ID" \
  --name "$EXPERIMENT_NAME"
```

从 prior best commit 继续：

```sh
printf '%s\n' "$ALAB_PROJECT_KEY" | alab --key-stdin exp create \
  --project "$ALAB_PROJECT_ID" \
  --name "$NEXT_EXPERIMENT_NAME" \
  --from-exp "$SOURCE_EXP_ID" \
  --from-commit best
```

## Worker Launch Pattern

```sh
env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY \
  ALAB_CMD_PREFIX="${ALAB_CMD_PREFIX:-alab}" \
  codex exec -C "$WORKTREE_PATH" \
  --sandbox workspace-write \
  - < "$WORKER_PROMPT"
```

如果 worker 必须读取 ignored example `.run` directory，可加：

```text
--add-dir "$RUN_DIR"
```

不要通过 argv、stdin prompt text、copied files 或 inherited environment 传递 project admin key。

## Closeout Report

Project controller 的最终报告应包含：

- project id 与 active config version；
- 创建或复用的 experiments；
- best experiment、run id、reward、parse status 和 commit；
- worker failures 与 skipped steps；
- 可安全分享的 report 或 artifact paths。
