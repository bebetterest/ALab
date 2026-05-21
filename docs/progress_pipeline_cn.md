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

## 当前 Active Batch - 2026-05-21

- Focus：shared-runner cleanup、project config/schema proof mapping、project/experiment hard-remove retained-row relationships、source/validation hard-remove audit/reference relationships、maintenance object audit metadata、credential model proof mapping、credential audit metadata、token revoke/regenerate side-effect mapping、context marker conflict/alias mapping、inspection context repair pinned-commit/audit metadata、public `--from-exp` visibility-intersection proof、explicit token/inspection observe visibility joins、run/artifact/log/annotation list filter/sort matrices，以及 experiment list/search filter/sort matrices 对当前 default/fake paths 关闭后，继续处理 grouped audit-row decomposition。
- 重复处理 guardrail：`docs/progress_closed_gaps.md` 现在负责 do-not-reopen list。只有下一批像已关闭 family 时才打开。
- 下一步 evidence：选择下一个能转成 direct proof 的 grouped audit row。

## Active Queue

| Priority | Batch | Why it is next | Evidence target | Suggested focused checks |
| --- | --- | --- | --- | --- |
| P0 | Grouped audit-row decomposition | Observe filter/sort matrices、credential model evidence、credential/token side-effect evidence、context marker conflict/alias mapping 和 inspection context repair pinned-commit metadata 现在已有 default-path direct evidence；剩余 evidence work 是仍需要在当前 object families 和未来 surfaces 上 final decomposition 的 grouped audit rows。 | Storage/auth/context audit rows，加剩余 grouped lifecycle evidence rows。 | 每次围绕一个 grouped audit row 增加窄 CLI/storage tests，继续从 direct proof 最弱的 object family 开始。 |
| P0 | Full default-suite gate | 当前 stale 时不能声称 completion。 | `docs/completion_audit.md` 的 P0 gate 和 `docs/progress.md` 的 gate snapshot。 | 只在下一批 code/test batch 后，或 completion claim 前立即运行。 |
| P1 | Real-environment runner gates | Release-quality validation 依赖目标机器和服务。 | Real-environment runner validation rows。 | 使用 `ALAB_RUN_REAL_DOCKER=1` 与相关 SkyDiscover/Harbor environment flags 运行 opt-in tests。 |
| P1 | Final docs consistency pass | Docs 应在 implementation 稳定后检查，而不是每个小 proof batch 后都全面处理。 | Documentation consistency rows。 | Markdown pair check、README tree sync、CLI spec sync，以及 README/AGENTS/specs/audit/progress manual pass。 |

## Guardrail 指针

不要在本文保存 detailed closed evidence。`docs/progress_closed_gaps.md` 只用于防止重复工作；`docs/completion_audit.md` 才是精确 evidence source。

当某个 batch 关闭了后续 agent 很可能重复处理的 gap 时，把简洁 closed family 加入 `docs/progress_closed_gaps.md`，并保持 audit row 的 direct evidence 最新。

## Full-Suite Policy

不要在每个小 edit 后都跑 full default suite。满足以下条件之一时再运行：

- Batch 改变 shared command dispatch、storage schema、runner services、visibility logic、lifecycle semantics 或 renderer behavior。
- Focused batch 关闭多个 audit rows，下一步要声称 completion 或 release-quality。
- 用户明确要求 full verification pass。

在此之前，只在 progress log 记录 focused verification，并保持 full-suite gate 为 stale。

## 更新 Checklist

1. 用 exact evidence 和 remaining action 更新相关 `docs/completion_audit.md` row。
2. 如果 gap 已关闭，删除或重写对应 active queue item。
3. 如果后续 agent 可能重复处理这个 closed proof family，就向 `docs/progress_closed_gaps.md` 添加简洁 guardrail。
4. 只有 gate state、top-level blocker 或 active focus 改变时，才更新 `docs/progress.md`。
5. 在 `docs/progress_log.md` 追加简洁 dated entry。
6. 将每个改动过的英文文档与对应 `*_cn.md` 同步。
