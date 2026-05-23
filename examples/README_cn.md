# ALab 示例

这些示例都从仓库根目录运行，生成状态保存在 ignored `.run/` 目录中。secrets
只写入 `.run/secrets/`。

## 总览

这些示例按复杂度从最小 local loop 到完整 agent 外部 benchmark 排列。每个示例都
是可运行项目 demo，并且任务形态、runner 边界和 evidence workflow 各不相同：

- [local_agent_scoreboard](local_agent_scoreboard/) 是最短 local loop：修改一个
  deterministic scorer，解析 stdout reward，捕获 artifacts，并提交结果。
- [docker_file_reward_artifacts](docker_file_reward_artifacts/) 是 container-only
  operations task：在 inventory、priority、cold-chain 和 split-shipment 约束下把
  诊所订单分配给仓库，然后导出 captured artifacts。
- [harbor_verifier_minimal](harbor_verifier_minimal/) 是 hidden-test task：改进
  incident urgency classifier，而 Harbor verifier 把 test cases 和详细日志保留在
  worker surface 之外。
- [collaboration_observe_lifecycle](collaboration_observe_lifecycle/) 是 project
  coordination task：创建 public experiments、从 prior best run 继续、标注 evidence、
  inspection prior commit，并 dry-run lifecycle cleanup。
- [skydiscover_circle_packing_codex](skydiscover_circle_packing_codex/) 是完整的
  Codex/SkyDiscover task：用隔离 worktree workers 改进 circle-packing benchmark，
  由 ALab 记录 runs、metrics、logs 和 reports。

学习某个示例时建议先运行 `--dry-run`。它会打印 command shape 和 paths，而不会
修改示例状态。

## 示例矩阵

| 示例 | Demo 任务 | Runner / adapter | 额外要求 | 主要覆盖 | 命令 |
| --- | --- | --- | --- | --- | --- |
| [local_agent_scoreboard](local_agent_scoreboard/) | 改进一个确定性评分 candidate，并提交最佳 run。 | local | 可选 Codex CLI | local runner、stdout reward、artifacts、submit、隔离 worker launch | `scripts/setup_project.sh`、`scripts/run_manual_demo.sh`、`scripts/run_codex_worker.sh` |
| [docker_file_reward_artifacts](docker_file_reward_artifacts/) | 基于库存、冷链和优先级约束构建容器化诊所订单履约计划器。 | Docker | Docker daemon | Dockerfile runner、file reward、manifest/summary artifacts、artifact export | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [harbor_verifier_minimal](harbor_verifier_minimal/) | 改进 incident-ticket urgency classifier，由 Harbor hidden verifier cases 评分。 | Harbor | Docker daemon | Harbor source import、private verifier assets、hidden verifier logs、Harbor reward | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [collaboration_observe_lifecycle](collaboration_observe_lifecycle/) | 协调两个 public incident-triage experiments，并从最佳 run 继续。 | local | ALab dev env 之外无额外要求 | public create、from-exp best、tags、annotations、inspection、remove dry-run | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [skydiscover_circle_packing_codex](skydiscover_circle_packing_codex/) | 用 Codex workers 改进 SkyDiscover circle-packing benchmark。 | SkyDiscover Python | Codex CLI、network、uv dependency install | SkyDiscover catalog、Python evaluator、controller/worker protocol | `scripts/setup_project.sh`、`scripts/run_single_worker.sh`、`scripts/run_controller.sh` |

## 建议阅读路径

先从 `local_agent_scoreboard` 理解基本 project/run/submit loop。然后看
`collaboration_observe_lifecycle` 理解 experiment lineage 和 observe commands。
需要验证 runner/verifier 边界时，再看 `docker_file_reward_artifacts` 和
`harbor_verifier_minimal`。需要完整 Codex worker/controller protocol 时，看
`skydiscover_circle_packing_codex`。

## 隔离模式

当示例启动 Codex 时，worker 使用 experiment worktree 作为 `codex exec -C`，
并使用 `--sandbox workspace-write`。worker launch 不会加入 repository root、整个 `.run/`、`.run/secrets` 或
`project.env`。它们只加入 `alab run`/`submit` 状态写入所需的 ALab home/cache
目录，以及非秘密 shared directories。

controller process 可以通过环境变量接收 project admin key，但不能把该 key、
root key、secret files 或 secret directories 传递给 worker process。
