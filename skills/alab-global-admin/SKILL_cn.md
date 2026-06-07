---
name: alab-global-admin
description: 当需要使用 root key 管理 ALab home，包括 home bootstrap、root/admin credential management、project initialization、SkyDiscover catalog management、global cache 或 backup pruning，以及 audit inspection，但不直接做 experiment work 时使用。
---

# ALab Global Admin

## 概览

本 skill 用于 root-level ALab administration。Global admin 负责 ALab home setup、root credential rotation、project admin key create/revoke、project initialization、SkyDiscover catalog lifecycle、cache/backup pruning、global audit inspection，以及 root-only local read-only dashboard。

本 skill 不做 experiment implementation。创建 project、作为 setup 一部分创建 experiment，或发放 project admin key 后，后续 project-level operations 交给带 project admin key 和 `alab-project-controller` skill/instructions 的独立 session/thread；experiment implementation 交给位于 experiment worktree、带 `alab-experiment-worker` skill/instructions、且只使用该 experiment token context 的独立 session/thread。如果无法启动独立 session，则使用具备等价 project/worktree/token 隔离的 subagent 或 worker process。用户指令优先于此偏好；否则 root-admin session 应聚焦 root-scoped administration。

## Credential Rules

- 将 root key 视为只渲染一次的本地 secret。
- Root commands 优先使用 `--key-stdin`；避免在 logs 中出现 inline key arguments。
- 不把 raw root/admin keys 存入 tracked files、prompts、commits、screenshots、reports 或 command transcripts。
- 生成的 project admin keys 只保存到 ignored local secret files，例如 example-local `.run/secrets/` 目录，或用户批准的安全位置。
- 委派给独立 session/thread 或 subagent 时，只传递该任务和 scope 所需的 credential。Root keys 只留给 root-admin sessions。Project admin keys 只交给执行该 project 的 project-level 工作的 sessions。Experiment worktree 或 inspection tokens 只交给在该 experiment worktree 或 inspection checkout 中工作的 sessions。使用 ignored secret files、private environment variables 或 secure stdin，不要写进 prompts。
- 给被委派的 sessions 或 subagents 提供对应的 ALab skill/instructions：project-level work 使用 `alab-project-controller`，experiment worktree work 使用 `alab-experiment-worker`。
- Handoff 后，root/admin keys 不应进入 worker prompts、worker sandboxes、shared run directories 或非 secret reports。
- 如果 root key 丢失，ALab V1 无法恢复；不要尝试临时编辑 DB。

## 功能说明

这是一份能力指南，不是固定步骤。根据 administrative objective 使用合适能力：

- 只有 ALab home 不存在时才用 `alab auth init` bootstrap；用 `alab config show` 或 `alab config validate` 检查 home health。
- 对 local ALab/tooling suggestion、question 或 bug report，使用 `alab feedback` 存到 home 下，不新增数据库 rows；使用 root-only `alab feedback list|show|archive` triage 这些 file-backed records。
- 当 root 用户需要在 browser 中只读查看 local home 时，使用 `alab dashboard`。Dashboard 只用于 local-only inspection；不要分享 token URL，也不要把它用于 mutation workflow。
- 谨慎管理 root credentials。只有明确需要时才 rotate root，并把 replacement keys 视为只渲染一次的 secrets。
- 为被委派的 project-level sessions 创建、列出和 revoke project admin keys。Revoke 前先识别 key id、project scope 和预期影响。
- 使用 config files，从 local、Git、empty、Harbor 或 SkyDiscover sources 初始化 projects。只捕获一次 generated project admin key，只保存到 ignored secret 位置，并安全 handoff 给带 `alab-project-controller` skill/instructions 的 project-level session，绝不交给 experiment worker。
- Root-level setup 后如果还需要继续 project setup、experiment creation 或 experiment coordination，启动带 project admin key 和 `alab-project-controller` skill/instructions 的独立 project-level session。需要 worktree changes 时，在 experiment worktree 中启动带 `alab-experiment-worker` skill/instructions、且只使用该 experiment token context 的独立 session。如果不可用，则使用具备等价隔离的 subagent 或 worker process，而不是在 global-admin session 中直接完成这些工作。
- 当 project initialization 在 baseline validation 阶段失败时，保留 redacted logs，并区分 environment/capability failures 与 reward-contract failures，例如 non-numeric reward metrics。
- 管理 SkyDiscover catalog lifecycle，包括 exact commit pinning、不访问网络的 `show`、active-reference blockers，以及带 explicit confirmation 的 remove。
- 使用 cache、trash 和 backup prune commands 维护 global non-authoritative state。
- 查看 global 或 project audit records，验证敏感 lifecycle events、credential changes、catalog changes、cleanup 和 project initialization。
- Destructive removal 前尽量使用 dry-run；日常 experiment coordination 应交给带 project admin key 的 project-level session，worktree editing 应交给带 token context 的 experiment worktree session。

## Command Reference

Root-only actions、project initialization、catalog changes 或 cleanup 前，读取 [references/commands_cn.md](./references/commands_cn.md)。
