# Docker File Reward Artifacts 示例

这个示例展示 Docker runner、项目 Dockerfile、file reward 解析和精确 artifact
export，并把这些能力放在一个只能通过容器运行的计划任务中。

## Demo 任务

editable source 是一个诊所订单履约计划器。它读取
`source/data/orders.json` 和 `source/data/warehouses.json`，在 inventory、cold-chain、
priority 和 split-shipment 约束下把订单分配给仓库。

baseline 使用简单 FIFO strategy。`scripts/run_demo.sh` 会在 worktree candidate 中
改成 priority-aware compact strategy，为 critical orders 预留 express stock，
在 Docker 中运行 ALab，捕获 `manifest.json`、`summary.md` 和 `reward.json`，
然后导出一个 captured artifact。

任务形态：

- Editable file：`source/main.py`。
- Input data：`source/data/orders.json` 和 `source/data/warehouses.json`。
- Constraints：stock limits、cold-chain compatibility、priority weight、SLA
  pressure 和 split-shipment compactness。
- Baseline behavior：FIFO order allocation，不为 express stock 做 reservation。
- Demo improvement：priority-aware allocation、compact splits，并为 critical
  orders 预留 express stock。
- Reward source：`run:reward.json`，包含 `weighted_fill`、`completed_weight`、
  `cold_chain_success` 和 `compactness` 等 numeric metrics。该文件只能是
  string-to-finite-number map；解释和 case details 应写入 `summary.md` 等 artifact。
- Captured evidence：`manifest.json` 表示 allocation plan，`summary.md` 是
  human-readable digest，`reward.json` 用于 file reward 解析。

这个示例适合验证 Docker 边界，因为任务只通过 Dockerfile runner 运行。captured
artifact export 也展示了 ALab 保存的是精确 artifact bytes，而不是渲染后的摘要。

## 环境要求

- Docker daemon，并且可以构建或拉取 `python:3.11-alpine`。
- 使用本仓库默认 ALab Python 环境。

## 运行

```sh
examples/docker_file_reward_artifacts/scripts/setup_project.sh --dry-run
examples/docker_file_reward_artifacts/scripts/setup_project.sh
examples/docker_file_reward_artifacts/scripts/run_demo.sh
```

排障分层：

- ALab config/runner error：检查 `.run/logs/` 下的 redacted setup log，并确认
  `alab.project.toml` 仍指向 `run:reward.json`。
- Docker daemon 或 image error：先运行 `docker version`；Docker 可用性和 image
  pull/build 是环境前提，不是源码任务失败。
- Reward parse error：保持 `reward.json` 只包含 numeric metrics。诊断说明放入
  `summary.md` 或其他 captured artifact。
- uv/dependency error：脚本默认使用 `UV_DEFAULT_INDEX=https://pypi.org/simple`；
  先检查本地 package index 访问，再判断示例任务是否失败。

## 覆盖内容

- Dockerfile runner 和 Docker image cache 行为；
- 使用 `run:reward.json` 的 `reward.type = "file"`；
- 捕获 manifest/summary/reward artifacts 并执行 `artifacts export`；
- artifact bytes 是精确导出，不会自动 redaction。
