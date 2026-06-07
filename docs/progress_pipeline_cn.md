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

## 当前 Active Batch - 2026-06-07

- Focus：用户要求的 dashboard static presentation fixes 和 front-of-pipeline CI version synchronization gate 已在当前 worktree 关闭。Dashboard 现在会为每个有分 run 渲染红色 best-so-far reward trend series：当后续 run 没有产生新的最佳值时，继续沿用此前最佳值，同时保留独立 new-best marker/count behavior。Project detail sticky tabs 滚动时也会贴住 detail header，并使用不透明 full-width background；run detail KPI rows 也会为横向滚动条预留足够高度。CI 现在会在 lint、tests、opt-in gates 或 publish jobs 前先检查 package version synchronization。
- 本 batch 明确 non-goals：不改变 dashboard APIs、CLI command contracts、read-model pagination、storage schema、runner behavior、visibility rules、reward ranking semantics、package publishing semantics 或 release asset upload semantics。本 batch 只改变 static dashboard chart/detail/KPI layout presentation、CI preflight ordering gate 和 focused evidence。
- 重复处理 guardrail：`docs/progress_closed_gaps.md` 负责 do-not-reopen list。只有未来 batch 像已关闭 family 时才打开。
- 已新增 evidence：focused dashboard static frontend test、version synchronization script 和 CI ordering contract tests、针对当前版本 changelog section 的 dynamic release-note extraction test、针对 touched Python test files 的 focused `ruff`、sandbox full-suite dashboard-bind failure confirmation、elevated full default suite、full-suite skip listing、opt-in skipped-test subset、`git diff --check`，以及使用 `examples/dashboard_showcase/.run/alab-home` 的 in-app Browser verification，确认 `SkyDiscover Circle Packing` 的 #3 会继续沿用 #2 的最佳值，project detail tabs 贴住 header、没有半透明空白间隙，且 `Embedding reranker` run detail KPI cards 在横向滚动条上方完整显示。

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
