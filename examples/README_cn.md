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
- [dashboard_showcase](dashboard_showcase/) 会生成一个丰富的 ALab home，包含多个
  projects、experiments、runs、logs、artifacts、audit entries、feedback、caches、
  capabilities、catalogs 和 locks，用于 dashboard inspection。
- [skydiscover_circle_packing_codex](skydiscover_circle_packing_codex/) 是完整的
  Codex/SkyDiscover task：用隔离 worktree worker 改进 circle-packing benchmark，
  由 ALab 记录 runs、metrics、logs 和 reports。
- [templates](templates/) 是模板库，不是单个 demo：可以复制其中一个
  multi-instance TSP 模板，直接获得完整的 local、Docker、Harbor、SkyDiscover
  Python 或 SkyDiscover Docker 项目骨架。

学习某个示例时建议先运行 `--dry-run`。它会打印 command shape 和 paths，而不会
修改示例状态。

## 示例矩阵

| 示例 | Demo 任务 | Runner / adapter | 额外要求 | 主要覆盖 | 命令 |
| --- | --- | --- | --- | --- | --- |
| [local_agent_scoreboard](local_agent_scoreboard/) | 改进一个确定性评分 candidate，并提交最佳 run。 | local | 可选 Codex CLI | local runner、stdout reward、artifacts、submit、隔离 worker launch | `scripts/setup_project.sh`、`scripts/run_manual_demo.sh`、`scripts/run_codex_worker.sh` |
| [docker_file_reward_artifacts](docker_file_reward_artifacts/) | 基于库存、冷链和优先级约束构建容器化诊所订单履约计划器。 | Docker | Docker daemon | Dockerfile runner、file reward、manifest/summary artifacts、artifact export | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [harbor_verifier_minimal](harbor_verifier_minimal/) | 改进 incident-ticket urgency classifier，由 Harbor hidden verifier cases 评分。 | Harbor | Docker daemon | Harbor source import、private verifier assets、hidden verifier logs、Harbor reward | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [collaboration_observe_lifecycle](collaboration_observe_lifecycle/) | 协调两个 public incident-triage experiments，并从最佳 run 继续。 | local | ALab dev env 之外无额外要求 | public create、from-exp best、tags、annotations、inspection、remove dry-run | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [dashboard_showcase](dashboard_showcase/) | 生成一个 rich ALab home，用于 root dashboard 浏览。 | local fixture | ALab dev env 之外无额外要求 | dashboard summary/detail data、projects、experiments、runs、logs、artifacts、audit、feedback、system diagnostics | `scripts/create_demo_home.py`、`scripts/run_dashboard.sh` |
| [skydiscover_circle_packing_codex](skydiscover_circle_packing_codex/) | 用单个 Codex worker 改进 SkyDiscover circle-packing benchmark。 | SkyDiscover Python | Codex CLI、network、uv dependency install | SkyDiscover catalog、Python evaluator、隔离 worker protocol | `scripts/setup_project.sh`、`scripts/run_single_worker.sh` |
| [templates](templates/) | 复制某个 runner family 的完整默认 multi-instance TSP 模板。 | local、Docker、Harbor、SkyDiscover Python、SkyDiscover Docker | 只有 Docker-bound 模板需要 Docker | reusable project configs、validation scripts、starter/reference solutions、setup/run scripts | `templates/<template>/scripts/setup_project.sh`、`templates/<template>/scripts/run_demo.sh` |

## 建议阅读路径

先从 `local_agent_scoreboard` 理解基本 project/run/submit loop。然后看
`collaboration_observe_lifecycle` 理解 experiment lineage 和 observe commands。
如果想用浏览器查看一个已填充的 local home，可以使用 `dashboard_showcase`。需要验证
runner/verifier 边界时，再看 `docker_file_reward_artifacts` 和
`harbor_verifier_minimal`。需要完整 single-worker Codex/SkyDiscover flow 时，看
`skydiscover_circle_packing_codex`。需要可复制的默认项目骨架，而不是完整场景
walkthrough 时，看 `templates`。

## 隔离模式

当示例启动 Codex 时，worker 使用 experiment worktree 作为 `codex exec -C`，
并使用 `--sandbox workspace-write`。worker launch 不会加入 repository root、整个 `.run/`、`.run/secrets` 或
`project.env`。它们只加入 `alab run`/`submit` 状态写入所需的 ALab home、uv
cache、pycache 和非秘密 shared directories。只有 worktree 是 editable source
surface；额外 side directories 只是 CLI state。

setup scripts 可以把 project admin key 保存到 ignored `.run/secrets/`，但 worker
processes 不能收到该 key、root keys、secret files 或 secret directories。
