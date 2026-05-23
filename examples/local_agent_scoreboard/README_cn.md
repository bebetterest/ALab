# Local Agent Scoreboard 示例

这个示例用一个很小的确定性 Python candidate 展示 ALab local runner。它是检查
project、run、artifact 和 submit 常规流程最快的示例。

## Demo 任务

改进 `source/solution.py`，让它输出更高的确定性 score、捕获 `score.json`，
并提交最佳 run。manual demo 会把 candidate 从 baseline strategy 改成一个确定性
improvement；可选 Codex worker 则在窄权限 experiment worktree 内完成同类任务。

任务形态：

- Editable file：`source/solution.py`。
- Baseline behavior：`SCORE = 0.40`，stdout 输出 `reward=0.400`。
- Demo improvement：`scripts/run_manual_demo.sh` 把 strategy 和 score 改到
  `0.82`，然后运行并提交 candidate。
- Reward source：stdout regex `reward=([0-9.]+)`。
- Captured evidence：`run:score.json` 以及 workspace 中的 `solution.py`。

这个示例刻意保持很小。它最适合用来观察 ALab 如何创建 experiment worktree、
写入 worktree token、捕获 logs/artifacts，并用 `alab submit` 关闭 experiment。

## 覆盖内容

- 使用 sanitized environment 的 local runner；
- stdout regex reward 解析；
- 从 `ALAB_RUN_DIR` 捕获 run artifact；
- 使用 worktree token 执行 run 和 submit；
- 可选的窄权限 Codex worker 启动方式。

## 运行

在仓库根目录执行：

```sh
examples/local_agent_scoreboard/scripts/setup_project.sh --dry-run
examples/local_agent_scoreboard/scripts/setup_project.sh
examples/local_agent_scoreboard/scripts/run_manual_demo.sh
```

可选 Codex worker：

```sh
examples/local_agent_scoreboard/scripts/run_codex_worker.sh --dry-run
examples/local_agent_scoreboard/scripts/run_codex_worker.sh
```

生成状态都在 ignored `.run/` 下。project admin key 只写入
`.run/secrets/project.env`；Codex worker 不会获得这个目录。

## 隔离说明

Codex worker 命令以 experiment worktree 作为 `-C`，只额外加入 ALab home/cache
和 `.run/shared` 作为可写目录。它不会加入 repository root、整个 `.run/` 或
`.run/secrets`。
