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

## 当前 Active Batch - 2026-06-04

- Focus：当前 worktree 已关闭本轮要求的 stable-boundary `services.py` extraction。Auth/root-key/admin-key handlers 现在位于 `src/alab/credentials.py`；backup/cache prune handlers 现在位于 `src/alab/maintenance.py`；annotation handlers 位于 `src/alab/annotations.py`；observe run/artifact/log handlers 位于 `src/alab/observe.py`；Markdown report export 位于 `src/alab/report.py`；source command handlers 位于 `src/alab/sources.py`；project config/env/secret handlers 位于 `src/alab/project_config.py`；project validation handlers 位于 `src/alab/project_validation.py`；experiment list/search/show/best handlers 位于 `src/alab/experiment_query.py`；experiment archive/unarchive/remove handlers 位于 `src/alab/experiment_lifecycle.py`；experiment worktree/token/checkout handlers 位于 `src/alab/experiment_access.py`；shared trash/removal staging 位于 `src/alab/removal.py`；SkyDiscover catalog handlers 和 catalog/adapter-ref resolution helpers 继续位于 `src/alab/catalog.py`；shared audit-event writing 继续位于 `src/alab/service_audit.py`；dashboard command handler 继续位于 `src/alab/dashboard.py`；audit handlers 继续位于 `src/alab/audit.py`；feedback handlers 继续位于 `src/alab/feedback.py`；shared request auth gates 继续位于 `src/alab/service_auth.py`；shared text/reason validation 继续位于 `src/alab/service_text.py`。已抽出 surfaces 的 registered CLI behavior 保持不变。
- 本 batch 明确 non-goals：不继续做大范围一次性 object-family extraction；在 shared helper boundaries 准备好之前，不拆 project init、与 experiment creation 共享的 source bootstrap、global config、context、run/submit、project list/show/archive/remove/locks、experiment create/tags 或 remaining core lifecycle helpers；不改变 annotation visibility/edit rules、observe run/artifact/log filters、hidden-log access、archive/remove semantics、report output shape、source import/remove semantics、project config semantics、validation semantics、experiment visibility/query ranking semantics、worktree/token/checkout semantics、SkyDiscover catalog behavior、dashboard behavior、feedback behavior、JSON CLI output、hosted/remote dashboard behavior 或新的 runner families。
- 重复处理 guardrail：`docs/progress_closed_gaps.md` 负责 do-not-reopen list。只有未来 batch 像已关闭 family 时才打开。
- 已新增 evidence：focused project config/env/secret、project validation、experiment observe/query、experiment lifecycle/remove、experiment worktree/token/checkout、removal/trash、auth/key、maintenance backup/cache、source/observe/annotation 和 registry-derived CLI contract checks；focused smoke regression checks 覆盖 transaction rollback 和 visibility/access edges；full relevant ruff checks；对 changed modules 强制 `compileall`；docs/audit sync checks；以及当前 stable-boundary extraction 的 elevated full default-suite pass。

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
