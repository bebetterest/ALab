# ALab + SkyDiscover Circle Packing + Codex 示例报告

这个示例展示 ALab 的 agent-first workflow：先用 ALab 初始化一个
SkyDiscover 项目，再让 Codex 在 ALab experiment worktree 中改代码、运行评估、
观察结果。

示例任务选用官方 SkyDiscover Quick Start 里的
`benchmarks/math/circle_packing`。任务目标是在单位正方形中放置 26 个不重叠圆，
最大化半径和。官方说明中的目标值是 `2.635`，ALab 使用 SkyDiscover evaluator
返回的 `combined_score` 作为 reward。

## Demo 任务

改进 SkyDiscover circle-packing initial program，同时保持公开的 `run_packing()`
contract。single-worker 脚本会在 token-scoped experiment worktree 中启动一个
Codex worker。

任务形态：

- Editable file：从 SkyDiscover benchmark 导入的 `initial_program.py`。
- Public contract：`run_packing()` 必须返回 `(centers, radii, sum_radii)`，表示
  单位正方形内 exactly 26 个不重叠圆。
- Evaluator：来自 pinned catalog bundle 的 SkyDiscover Python evaluator。
- Reward source：SkyDiscover `combined_score`，由 valid radius sum 相对 target
  value `2.635` 决定。
- Worker boundary：Codex workers 只编辑 experiment worktree，并使用 worktree
  token 执行 `alab run`；它们不会收到 project admin key。
  ALab home、uv cache、pycache 和 `.run/shared` 只作为 CLI state directories
  加入，不是 editable source。
- Report output：`collect_report.sh` 读取本地 ALab records，并把 baseline/run
  metrics 汇总到 `.run/reports/report.md`。

这是最完整的 external-agent orchestration demo。它展示 ALab 如何记录客观
evaluation evidence，同时让外部 agent 在受限 worktree 内搜索代码方案。

官方来源：

- SkyDiscover: https://github.com/skydiscover-ai/skydiscover
- Circle Packing benchmark: https://github.com/skydiscover-ai/skydiscover/tree/main/benchmarks/math/circle_packing
- 本示例固定 catalog commit：`c0f6b704a05d883b61eff261023f61897cb45711`

## 1. 这个示例验证什么

它不是 ALab 内置 agent launcher。ALab V1 仍然只负责本地 project、experiment、
runner、records 和 visibility；Codex 是外部 agent。这个示例验证的是二者如何
组合：

- human 初始化 ALab home、SkyDiscover catalog 和 project；
- ALab 从 SkyDiscover benchmark 的 initial program 创建 editable source；
- Codex worker 在 ALab worktree 中只编辑 `initial_program.py`；
- worker 用 worktree token 调用 `alab run`，不需要 project key；
- ALab 记录 baseline、runs、metrics、reward、logs 和 best result；
- `collect_report.sh` 生成本地小报告 `.run/reports/report.md`。

## 2. 环境要求

从仓库根目录运行：

```sh
uv run alab help
codex --help
git --version
```

还需要：

- Python 3.11+；
- 可访问 `https://github.com/skydiscover-ai/skydiscover.git`；
- `uv` 能为 SkyDiscover Python evaluator 安装依赖；
- 已登录并可用的 Codex CLI；
- 可选设置 `CODEX_MODEL`；不设置时使用本机 Codex 默认模型。

真实 key 处理规则：

- `root key` 只用于 setup，不写入 `.run/secrets/project.env`；
- `project admin key` 写入 ignored `.run/secrets/project.env`；
- worker 通过 worktree token 运行，脚本用
  `env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY -u ALAB_KEY` 移除 admin/root keys；
- README、报告和 redacted log 不记录真实 key。

## 3. 文件说明

```text
examples/skydiscover_circle_packing_codex/
├── alab.project.toml
├── prompts/
│   └── worker.md
├── scripts/
│   ├── setup_project.sh
│   ├── run_single_worker.sh
│   └── collect_report.sh
├── README.md
└── README_cn.md
```

运行后会生成 ignored `.run/`：

```text
.run/
├── alab-home/
├── logs/
├── reports/
├── secrets/
│   └── project.env
├── shared/
├── setup-summary.md
├── uv-cache/
└── worktrees/
```

## 4. 项目配置

`alab.project.toml` 的关键部分：

```toml
[mutable]
include = ["initial_program.py"]

[runner]
type = "skydiscover_python"
timeout_seconds = 900
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/math/circle_packing"
program_path = "initial_program.py"

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
```

这个配置让 agent 只能修改 `initial_program.py`。SkyDiscover evaluator 仍然来自
hidden catalog bundle，不会作为 editable source 暴露给 worker。

## 5. 初始化项目

先做 dry-run 看路径和命令：

```sh
examples/skydiscover_circle_packing_codex/scripts/setup_project.sh --dry-run
```

真实初始化：

```sh
examples/skydiscover_circle_packing_codex/scripts/setup_project.sh
```

脚本执行：

```sh
alab auth init
alab catalog skydiscover add --commit c0f6b704a05d883b61eff261023f61897cb45711
alab project init skydiscover --config examples/skydiscover_circle_packing_codex/alab.project.toml
```

初始化成功后查看：

```sh
source examples/skydiscover_circle_packing_codex/.run/secrets/project.env
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" project show --project \"\$ALAB_PROJECT_ID\""
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" project config show --project \"\$ALAB_PROJECT_ID\""
```

预期现象：

- project status 是 `valid`；
- validation status 是 `passed`；
- runner type 是 `skydiscover_python`；
- output 会提示 Python evaluator 不是 OS sandbox；
- `.run/logs/03-project-init.redacted.log` 不包含真实 project key。

如果要从头重跑：

```sh
examples/skydiscover_circle_packing_codex/scripts/setup_project.sh --reset
```

## 6. 单 worker 实验

先做 dry-run：

```sh
examples/skydiscover_circle_packing_codex/scripts/run_single_worker.sh --dry-run
```

真实运行：

```sh
examples/skydiscover_circle_packing_codex/scripts/run_single_worker.sh
```

脚本会：

1. 创建 `codex-circle-single` experiment；
2. 进入该 experiment worktree；
3. 用 `prompts/worker.md` 启动 Codex；
4. worker 修改 `initial_program.py`；
5. worker 执行：

```sh
eval "$ALAB_CMD_PREFIX run --message 'codex circle-packing worker improvement'"
```

启动前，脚本会拒绝 repository root、整个 `.run` 目录或 `.run/secrets` 等不安全
的 `codex exec -C` path，以 `--sandbox workspace-write` 运行 Codex，并检查额外
加入的 writable side directories 都是非秘密 CLI state directories。

观察结果：

```sh
source examples/skydiscover_circle_packing_codex/.run/secrets/project.env
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" runs list --project \"\$ALAB_PROJECT_ID\""
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" exp best --project \"\$ALAB_PROJECT_ID\""
```

## 7. 生成报告

setup 或 worker run 之后运行 report collector：

```sh
examples/skydiscover_circle_packing_codex/scripts/collect_report.sh
```

输出：

```text
examples/skydiscover_circle_packing_codex/.run/reports/report.md
```

报告包含：

- baseline validation；
- 每个 run 的 experiment、status、reward；
- SkyDiscover metrics：`sum_radii`、`target_ratio`、`validity`、`eval_time`；
- best experiment、best run、best commit；
- command log 路径。

结果表模板：

| phase | name | status | reward | sum_radii | target_ratio | validity | eval_time | run id | commit |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| baseline | `<validation_id>` | `<passed>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` |  |  |
| run | `codex-circle-single` | `<passed/failed/error>` | `<combined_score>` | `<sum_radii>` | `<target_ratio>` | `<validity>` | `<seconds>` | `<run_id>` | `<commit>` |

不要手写或猜测结果。未实跑时表格保留占位；实跑后以 `.run/reports/report.md`
和 ALab records 为准。

本地确认快照（2026-05-22，单 worker 流程）：

| phase | name | status | reward | sum_radii | target_ratio | validity | eval_time |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | `val-baseline-*` | passed | 0.364237 | 0.959764 | 0.364237 | 1.000000 | 0.201229 |
| run | `codex-circle-single` | passed | 0.998590 | 2.631286 | 0.998590 | 1.000000 | 0.090970 |

该 run 由 Codex worker 先在实验 worktree 中生成固定 packing，再由真实
SkyDiscover Python evaluator 写入本地 `.run/alab-home` 记录。具体 run id、commit
和 log 路径以本机 `.run/reports/report.md` 为准。

## 8. 记录效果时看什么

核心指标：

- `combined_score`：ALab reward，越大越好；
- `sum_radii`：26 个圆半径和；
- `target_ratio`：`sum_radii / 2.635`；
- `validity`：约束是否满足；
- `eval_time`：evaluator 用时。

判断方式：

- worker run 是否超过 baseline；
- worker 是否保持 circle-packing constraints 有效；
- failed/error run 是否仍有可解释日志；
- best result 是否由 ALab records 支撑，而不是只来自 agent 自述。

## 9. Log 和排障

主要 log：

```text
.run/logs/01-auth-init.redacted.log
.run/logs/02-catalog-add.log
.run/logs/03-project-init.redacted.log
.run/logs/single-worker.log
.run/logs/report-runs-list.log
.run/logs/report-best.log
```

常见问题：

- ALab setup/config error：检查 `.run/logs/03-project-init.redacted.log`；只有在
  project state 可丢弃时才运行 `setup_project.sh --reset`。
- `active SkyDiscover catalog not found`：重新运行 `setup_project.sh`。
- GitHub/network error：检查网络或代理；catalog clone 是必需步骤，而且它和
  ALab runner 正确性是两类问题。
- dependency install 失败：确认 `uv` 可访问 Python package index。示例默认使用
  `UV_DEFAULT_INDEX=https://pypi.org/simple`。
- Codex 未登录：先运行 `codex login` 或修复本地 Codex 配置。
  Codex 登录或网络失败是外部 agent runtime 问题，不是 ALab evaluator failure。
- worker 中 `alab help` 显示 `context type: none`：确认 worker 的 `codex exec`
  命令加入了 `$ALAB_EXAMPLE_HOME`、`$UV_CACHE_DIR` 和
  `$PYTHONPYCACHEPREFIX`；不要加入整个 `.run/` 或 `.run/secrets`。
- worker 修改了非 `initial_program.py` 文件：ALab mutable scope 会拒绝 run。
- worker 输出 key：停止运行，删除 `.run/`，重新 setup，并检查 prompt/日志。

## 10. 清理

删除本示例所有本地运行数据：

```sh
rm -rf examples/skydiscover_circle_packing_codex/.run
```

这不会删除仓库里的示例文件。
