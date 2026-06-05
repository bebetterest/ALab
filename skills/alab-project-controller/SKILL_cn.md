---
name: alab-project-controller
description: 当需要使用 project admin key 管理一个已有 ALab project、创建和协调 experiments、验证或调整 project config、管理 project-scoped source/lifecycle state，并在不暴露 admin credential 的前提下启动 worker agents 时使用。
---

# ALab Project Controller

## 概览

当 Codex 需要用 project admin key 协调一个 ALab project 时使用本 skill。Controller 负责创建 experiments、在 worktrees 中启动 worker agents、观察 project-visible evidence、比较 best runs，并管理 project-scoped config 与 lifecycle operations。

本 skill 不是 global administrator。不得初始化 ALab home、轮换 root credential、管理 SkyDiscover catalog、prune global cache/backup，或创建/revoke project admin keys。

## Credential Rules

- Project admin key 只能来自私有 environment variable 或 secure stdin。
- ALab admin commands 优先使用 `--key-stdin`；避免在可能被记录的 command 中写 inline key。
- 永不打印、提交、写入 prompt，或传递 project admin key 给 workers。
- 启动 worker 时，从 worker environment 中移除 admin/root credentials：

```sh
env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY \
  codex exec -C "$WORKTREE_PATH" --sandbox workspace-write - < "$WORKER_PROMPT"
```

- 如果 worker 需要 ALab CLI state writes，只加入 `alab run` 或 `submit` 必需的具体 ALab home/cache/shared directories；不要加入 repository root、整个 `.run`、`.run/secrets`、`project.env`，或任何包含 admin/root keys 的目录。启动前预检 worker path，并拒绝把 repo root、`.run` 或 secret paths 作为 `codex exec -C`。

## 功能说明

这是一份能力指南，不是固定步骤。根据 project objective 使用合适能力：

- 用 `alab project show`、`alab project config show`、`alab status` 以及 project-scoped audit/observe commands 检查 project state。
- 对于 ALab/tooling suggestion、question 或 bug report，使用 `alab feedback` 存到 local home，而不是混入 project annotations。
- 在 default source、explicit sources 或可见 predecessor experiments 基础上创建新 experiments；需要延续时再使用 from-experiment。
- 记录 experiment ids、worktree paths、source refs、tags、from-experiment choices，以及 `best`、`final`、`latest` 等 selected commits，保持 experiment lineage 清楚。
- 在 experiment worktrees 中启动 worker agents，但不传递 project admin 或 root credentials。只提供任务说明和非 secret helper variables；让 worker 使用自己的 worktree token 执行 `alab run` 和 `alab submit`，尽量收窄 writable side directories，并说明额外目录是 CLI state 而不是 editable source。
- 如果 project 使用 free evaluation（`runner.type = "none"` 且 `reward.type = "none"`），应告知 workers 不运行 `alab run`，直接 submit；final run id 会是 `none`，结果不会进入 best reward ranking。
- 跨 experiments、runs、artifacts、logs 和 annotations 观察 project-visible evidence。优先依据 reward、parse status、warning codes、metrics、best/final commits 和 submitted refs，而不是 free-form worker claims。
- 先把 reward parse failures 当作 contract failures 处理。对于 file 或 Harbor rewards，检查 reward JSON 是否只包含 finite numeric metrics，并把详细 diagnostics 放到 artifacts 或 hidden/visible logs 中。
- 只有 requested project objective 需要时，才管理 project-scoped config、environment variables、secrets、validation、sources、tags 和 lifecycle state。
- Destructive lifecycle actions 前先使用 dry-run remove，并在 force/confirm 前记录 blockers 或 cleanup 后果。
- Controller summary 应说明创建或改变了什么、哪些 experiments/runs 重要、哪些 credentials 被刻意 withheld from workers，以及剩余 follow-up。

## Command Reference

使用 project-scoped admin commands、启动 workers 或执行 lifecycle cleanup 前，读取 [references/commands_cn.md](./references/commands_cn.md)。
