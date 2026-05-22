# ALab Experiment Worker Commands

## 允许的 Surface

在 active experiment worktree 内使用这些 commands：

```text
alab status
alab help
alab run --message "<message>"
alab submit --message "<message>" --summary "<text>" --feedback "<text>" --ref none
alab observe experiments list|search|show|best ...
alab observe runs list|show ...
alab observe artifacts list|show|export ...
alab observe logs list|show|export ...
alab observe annotations list|show ...
alab annotate add|edit|archive|unarchive ...
```

Worker lifecycle 权限有意保持很窄：

- `run` 和 `submit` 需要当前 experiment 的 valid worktree token。
- Observe commands 只显示当前 token 可见的 records。
- Hidden logs 需要 root/admin，不属于本 skill。
- Worker annotation mutation 只限于 visible targets 和由该 worker token 创建的 annotations。

## 功能明细

每项说明功能、作用、关键参数和输出/注意点。

- **`alab status`**：检查当前 experiment/project 状态和 next action hint。
  关键参数：只有 controller 明确给出时才使用可选 `--project <project_id>`；通常在 worktree 内不带 flags 运行。
  输出用途：确认 context type、project id、experiment id、project status、experiment status，以及是否可继续工作。
- **`alab help`**：查看当前 worktree token 可用 commands。
  关键参数：`--all --explain` 可以显示 locked commands 和安全原因。
  输出用途：避免误用 admin/root commands，并识别可用 observe 或 annotation commands。
- **`alab run`**：评估当前 candidate，并保存 run evidence。
  关键参数：必需 `--message <text>`；保持简短且具体。
  输出用途：获取 run id、status、reward、parse status、warnings、previews、artifact count 和 next action。
- **`alab submit`**：在有 passed run 支撑后，提交最终 summary 和 feedback 并关闭 experiment。
  关键参数：必需 `--message`、`--summary`/`--summary-file` 二选一、`--feedback`/`--feedback-file` 二选一，以及至少一个 `--ref`；可选 `--rerun`。
  输出用途：获取 final run id、final commit、stored summary/feedback、experiment status 和 submitted refs。
- **`observe experiments list`**：查看 project 中当前 token 可见的 experiments。
  关键参数：Filters 包括 `--status`、重复 `--tag`、`--source-id`、`--name-query`、reward bounds、config version、timestamps 和 `--include-archived`；pagination 使用 `--limit`/`--offset`；sorting 使用 `--sort <field>:<asc|desc>`。
  输出用途：查找 prior attempts、similar tags、source lineage、closed experiments 和可能的 refs。
- **`observe experiments search`**：搜索可见 experiment corpus，寻找思路或历史失败。
  关键参数：必需 `--query <text>`，并可加主要 experiment filters。
  输出用途：定位相关 summary、feedback、task text、name、goal、tags 和 latest annotation bodies。
- **`observe experiments show`**：查看一个可见 experiment。
  关键参数：必需 `<exp_id>`。
  输出用途：确认 source ref、latest/final/best commits、tags、status，以及是否应作为 ref 引用。
- **`observe experiments best`**：按 reward policy 排序查找可见 best experiments。
  关键参数：可加 experiment filters；不支持 custom sort。
  输出用途：识别强 baseline 或 inspiration candidates，并注意 incomparable-run warnings。
- **`observe runs list`**：查看可见 run history。
  关键参数：Filters 包括 `--exp`、`--status`、`--config-version`、`--commit`、reward bounds、`--runner-type`、`--exit-code`、`--failure-reason-query`、timestamps 和 `--include-archived`。
  输出用途：比较 candidate 质量、定位 failure modes，或查看当前 experiment runs。
- **`observe runs show`**：查看一个可见 run。
  关键参数：必需 `<run_id>`。
  输出用途：读取 reward、parse status、warning codes、stdout/stderr previews、artifact count、hidden-log availability 和 timestamps。
- **`observe artifacts list/show/export`**：查看或导出可见 captured artifacts。
  关键参数：List filters 包括 `--exp`、`--run`、`--validation`、`--root workspace|run`、`--status`、`--path-query`、`--content-hash`、size bounds、timestamps 和 `--include-archived`；export 需要 `<artifact_id> --out <path>`，可选 `--overwrite`/`--include-archived`。
  输出用途：检查 outputs、generated reports 或解释 prior results 的文件。
- **`observe logs list/show/export`**：查看或导出可见 logs。
  关键参数：List filters 包括 `--exp`、`--run`、`--validation`、`--stream stdout|stderr|hidden_stdout|hidden_stderr`、`--truncated`、timestamps 和 archive flags。Worker tokens 不能使用 hidden logs。
  输出用途：用可见 stdout/stderr content 和 previews 诊断失败。
- **`observe annotations list/show`**：读取可见 notes 和 review comments。
  关键参数：List filters 包括 `--target-type`、`--target-id`、`--author`、`--created-by`、`--private`、`--query`、timestamps 和 `--include-archived`；show 接受 `<annotation_id>` 和可选 `--history`。
  输出用途：捕获 prior guidance、known issues，以及挂在 experiments、runs、artifacts 上的 rationale。
- **`annotate add/edit/archive/unarchive`**：添加或维护 worker-visible notes。
  关键参数：`add` 需要 `--target <target>` 和 `--body`/`--body-file` 二选一；可选 `--author`、`--private`。`edit` 需要 `<annotation_id>` 和一个 body input。Archive/unarchive 需要 `<annotation_id>`。
  输出用途：给后续 workers 留下有用证据，不改变 project configuration。

## 可见历史

Worker 可以在决定修改方向前，用 ALab observe commands 研究可见范围内的历史 experiments：

```text
alab observe experiments list
alab observe experiments search --query "<keyword>"
alab observe experiments best
alab observe experiments show <exp_id>
alab observe runs list --exp <exp_id>
alab observe runs show <run_id>
alab observe artifacts list --exp <exp_id>
alab observe logs list --exp <exp_id>
alab observe annotations list --target-type experiment --target-id <exp_id>
```

可见历史用于提供证据和灵感，不用于扩展权限。优先参考 high-reward passed runs、有用 warning patterns、清晰 annotations，以及可比较的 task/source lineage。如果某个 prior experiment 对最终答案有实质影响，应在 submit 时把它作为 ref。

## 禁止的 Surface

Worker role 不要运行这些 commands：

```text
alab auth ...
alab key ...
alab project config ...
alab project env ...
alab project secret ...
alab project validate ...
alab project remove ...
alab source remove ...
alab catalog ...
alab cache prune ...
alab backup prune ...
alab audit ...
alab exp remove ...
alab exp worktree remove|restore ...
alab exp token ...
```

如果确实需要其中某项能力，应报告给 project controller 或 global admin。

## Evaluation Pattern

```text
alab status
alab run --message "try focused improvement"
alab observe runs show <run_id>
```

使用可见 stdout/stderr preview、warning code、artifact 和 log 诊断。除非用户明确把你切换到 admin role，不要请求 hidden evaluator logs。

## Submit Pattern

summary 和 feedback 超过一句话时，优先写入临时文件：

```text
alab submit \
  --message "final candidate" \
  --summary-file /tmp/alab-summary.txt \
  --feedback-file /tmp/alab-feedback.txt \
  --ref none
```

只有没有历史 experiment 对结果产生实质影响时，才使用 `--ref none`。如果可见 experiments 确实影响了结果，应显式重复传入 refs：

```text
alab submit \
  --message "final candidate" \
  --summary-file /tmp/alab-summary.txt \
  --feedback-file /tmp/alab-feedback.txt \
  --ref <exp_id_that_inspired_or_was_continued> \
  --ref <another_relevant_exp_id>
```

summary 应描述最终改动和支撑它的 passed run。feedback 应包含有用的操作备注：关键 metrics、避开的 failure modes、每个 ref 为什么相关，以及剩余风险。不要包含 raw tokens、hidden-log content 或不可访问的 experiment ids。

Worker 的最终回复应包含：

- 调整过的策略或实现区域；
- final run id 和 status；
- reward 与关键 metrics；
- 使用的 submit refs，或说明为什么是 `ref none`；
- 如果 ALab 渲染了 final commit，则记录它；
- 剩余风险或已知失败。
