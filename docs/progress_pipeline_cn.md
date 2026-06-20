# ALab 实现 Pipeline

本文是 ALab V1 的 active work queue。`docs/progress.md` 保持短 dashboard；历史细节放在 `docs/progress_log.md`；closed proof guardrails 放在 `docs/progress_closed_gaps.md`；requirement evidence 放在 `docs/completion_audit.md`。

## 操作规则

- 每个 batch 从本文开始，不从历史日志或 closed-gap guardrails 开始。
- 添加工作前，先检查 `docs/completion_audit.md` 中对应 audit row。
- 如果 planned batch 像已经关闭的 proof family，实施前先检查 `docs/progress_closed_gaps.md`。
- 将相关 edits 合并成批，并为整批运行 focused tests；只有 batch 明显改变共享行为时才跑更宽的 checks。
- Batch 后更新顺序：`docs/completion_audit.md`、本文、如果关闭了可复用 guardrail 则更新 `docs/progress_closed_gaps.md`、如果 gate-level state 改变则更新 `docs/progress.md`，最后更新 `docs/progress_log.md`。
- 本文只保留当前 queue 和 update policy。不要追加 stale backlog；evidence 关闭时直接改写或删除 queue rows。
- 英文文档是 canonical。必须在同一个 change 中更新同步的 `*_cn.md` 文件。

## 当前 Active Batch - 2026-06-20

- Focus：用户要求的 project reference metrics 和 dashboard metric curves 已在当前 worktree 关闭。Project configs 现在支持 optional `[metrics].reference` entries，并校验 metric names、labels、units 与 maximize/minimize direction；缺少 optional metrics section 的 legacy configs 仍会通过 canonical config contract 加载。`project config show` 会渲染 configured reference metrics，local/Docker reward extraction 会把 primary 或完整 JSON numeric metrics 写入 run/validation records，root dashboard read model/frontend 会在 reward trend 旁为每个 configured reference metric 渲染 trend card。
- 本 batch 明确 non-goals：不做 database migration、不改变 ranking/best-run semantics、不改变 lifecycle/visibility/source policy、不新增 dashboard mutation controls、不改变 hosted/non-loopback dashboard behavior，也不新增 runner type。本 batch 只改变 project-config schema/read output、local/Docker reward metric persistence、dashboard read models/static charts、documentation 和 focused evidence。
- 重复处理 guardrail：`docs/progress_closed_gaps.md` 负责 do-not-reopen list。只有未来 batch 像已关闭 family 时才打开。
- 已新增 evidence：focused project config schema/migration contract tests、local runner JSON/full-metric persistence tests、dashboard read-model/static frontend tests、CLI success-field/docs synchronization checks、config/run flows smoke tests、local/Docker/Harbor/SkyDiscover full runner suites、相关 `ruff`、强制 `compileall`、dashboard JavaScript 的 `node --check`、full default suite `.venv/bin/python -m pytest -q`、docs/audit consistency checks，以及 `git diff --check`。

## Active Queue

当前 worktree 没有剩余 active queue。

未来 queue rows 必须先点名具体 changed requirement、command、option、invariant、warning/error code、lifecycle rule、visibility rule、runner contract、persistence contract、release-target environment 或 upstream catalog behavior，再开始 implementation。

## Guardrail 指针

不要在本文保存 detailed closed evidence。`docs/progress_closed_gaps.md` 只用于防止重复工作；`docs/completion_audit.md` 才是精确 evidence source。

当某个 batch 关闭了后续 agent 很可能重复处理的 gap 时，把简洁 closed family 加入 `docs/progress_closed_gaps.md`，并保持 audit row 的 direct evidence 最新。

## Full-Suite Policy

不要在每个小 edit 后都跑 full default suite。满足以下条件之一时再运行：

- Batch 改变 shared command dispatch、storage schema、runner services、visibility logic、lifecycle semantics 或 renderer behavior。
- Focused batch 关闭多个 audit rows，下一步要声称 completion 或 release-quality。
- 用户明确要求 full verification pass。

在此之前，只在 progress log 记录 focused verification。如果 implementation/test changes 发生在最近一次 full-suite pass 之后，再把 full-suite gate 标为 stale。

## 更新 Checklist

1. 用 exact evidence 和 remaining action 更新相关 `docs/completion_audit.md` row。
2. 如果 gap 已关闭，删除或重写对应 active queue item。
3. 如果后续 agent 可能重复处理这个 closed proof family，就向 `docs/progress_closed_gaps.md` 添加简洁 guardrail。
4. 只有 gate state、top-level blocker 或 active focus 改变时，才更新 `docs/progress.md`。
5. 在 `docs/progress_log.md` 追加简洁 dated entry。
6. 将每个改动过的英文文档与对应 `*_cn.md` 同步。
