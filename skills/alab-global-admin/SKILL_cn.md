---
name: alab-global-admin
description: 当需要使用 root key 管理 ALab home，包括 home bootstrap、root/admin credential management、project initialization、SkyDiscover catalog management、global cache 或 backup pruning，以及 audit inspection，但不直接做 experiment work 时使用。
---

# ALab Global Admin

## 概览

本 skill 用于 root-level ALab administration。Global admin 负责 ALab home setup、root credential rotation、project admin key create/revoke、project initialization、SkyDiscover catalog lifecycle、cache/backup pruning，以及 global audit inspection。

本 skill 不做 experiment implementation。创建 project 或发放 project admin key 后，应把 experiment coordination 交给 `alab-project-controller`，把 worktree changes 交给 `alab-experiment-worker`。

## Credential Rules

- 将 root key 视为只渲染一次的本地 secret。
- Root commands 优先使用 `--key-stdin`；避免在 logs 中出现 inline key arguments。
- 不把 raw root/admin keys 存入 tracked files、prompts、commits、screenshots、reports 或 command transcripts。
- 生成的 project admin keys 只保存到 ignored local files 或用户批准的安全位置。
- 如果 root key 丢失，ALab V1 无法恢复；不要尝试临时编辑 DB。

## 功能说明

这是一份能力指南，不是固定步骤。根据 administrative objective 使用合适能力：

- 只有 ALab home 不存在时才用 `alab auth init` bootstrap；用 `alab config show` 或 `alab config validate` 检查 home health。
- 谨慎管理 root credentials。只有明确需要时才 rotate root，并把 replacement keys 视为只渲染一次的 secrets。
- 为 project controllers 创建、列出和 revoke project admin keys。Revoke 前先识别 key id、project scope 和预期影响。
- 使用 config files，从 local、Git、empty、Harbor 或 SkyDiscover sources 初始化 projects。只捕获一次 generated project admin key，并安全 handoff。
- 管理 SkyDiscover catalog lifecycle，包括 exact commit pinning、不访问网络的 `show`、active-reference blockers，以及带 explicit confirmation 的 remove。
- 使用 cache、trash 和 backup prune commands 维护 global non-authoritative state。
- 查看 global 或 project audit records，验证敏感 lifecycle events、credential changes、catalog changes、cleanup 和 project initialization。
- Destructive removal 前尽量使用 dry-run；日常 experiment coordination 或 worktree editing 应交给 project controller 和 experiment worker roles。

## Command Reference

Root-only actions、project initialization、catalog changes 或 cleanup 前，读取 [references/commands_cn.md](./references/commands_cn.md)。
