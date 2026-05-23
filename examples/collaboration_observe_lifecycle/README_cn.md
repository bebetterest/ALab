# Collaboration Observe Lifecycle 示例

这个示例使用 local runner 展示 ALab collaboration 行为：public experiment
creation、`--from-exp best`、tags、annotations、inspection checkout、archive 和
remove dry-run。

## Demo 任务

editable source 是一个 incident triage scheduler。它读取
`source/data/incidents.json`，在十小时 response budget 下排序处理事项，并写出
`result.json` 和 `triage_plan.md`。

`scripts/run_demo.sh` 会创建第一个 public experiment，把 queue order 改成
severity-first triage 并提交。然后它从第一个 experiment 的 best commit 创建第二个
public experiment，启用 runbook shortcuts 和 security escalation，记录 tag 和
annotation，创建 inspection checkout，archive 第一个 experiment，并 dry-run cascade
removal。

任务形态：

- Editable file：`source/solver.py`。
- Input data：`source/data/incidents.json`，其中包含 severity、category、SLA、
  affected users 和 runbook metadata 等 synthetic operations queue。
- Baseline behavior：按创建顺序处理 incidents，会错过紧急 SLA/security work。
- Step 1 improvement：在 public experiment 中改为 `severity_first` ordering，然后
  `alab submit`。
- Step 2 improvement：从 step 1 的 `best` commit 创建第二个 public experiment，
  切换到 SLA-balanced ranking，启用 runbook shortcuts，并提升 security incidents
  优先级。
- Captured evidence：`result.json`、`triage_plan.md`、run logs、experiment tag、
  annotation、inspection checkout、archive output 和 remove dry-run output。

这个示例重点不是单一 runner feature，而是 project coordination。它展示 controller
如何保持 lineage 和 evidence 可见，同时让 workers 只通过自己的 worktree tokens
操作。

## 运行

```sh
examples/collaboration_observe_lifecycle/scripts/setup_project.sh --dry-run
examples/collaboration_observe_lifecycle/scripts/setup_project.sh
examples/collaboration_observe_lifecycle/scripts/run_demo.sh
```

## 覆盖内容

- no-key public `exp create` bootstrap；
- 使用 `--from-exp <exp_id> --from-commit best` 继续前序实验；
- 从 worktree 中使用 token-scoped run、tag、annotation 和 artifact-producing commands；
- admin inspection checkout 和 lifecycle dry-run；
- `.run/logs` 下的 observe evidence logs。

## 安全说明

project admin key 只存放在 `.run/secrets/project.env`。worktree 操作使用 ALab
写入各 experiment worktree 的 token。
