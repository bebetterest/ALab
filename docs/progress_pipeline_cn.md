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

## 当前 Active Batch - 2026-05-22

- Focus：storage/audit/object retained-relationship proof、core successful workflow proof、CLI golden/command-contract completeness、capability/help/payload preflight proof、runtime stack/architecture proof、host-support policy proof、documentation consistency proof、source/public experiment direction proof、runner/adapter direction proof、当前 Darwin real Docker-backed runner 与 capability-refresh validation、run/submit lifecycle proof、lifecycle archive/unarchive/remove evidence mapping、home/filesystem/path-registry evidence mapping、exp-create source-binding/default-source proof、source import canonical tree-hash/remote-Git fidelity proof、project init precedence proof mapping、config edit semantics proof mapping、public `--source-git` credential-helper warning proof、context repair old-path blocker proof、security boundary negative proof、config capability-refresh evidence mapping、shared-runner cleanup、project config/schema proof mapping、project/experiment hard-remove retained-row relationships、source/validation hard-remove audit/reference relationships、maintenance object audit metadata、credential model proof mapping、credential audit metadata、token revoke/regenerate side-effect mapping、context marker conflict/alias mapping、inspection context repair pinned-commit/audit metadata、public `--from-exp` visibility-intersection proof、explicit token/inspection observe visibility joins、run/artifact/log/annotation list filter/sort matrices、experiment list/search filter/sort matrices，以及 final default-suite gate 已对当前 default/fake paths 完成 closeout validation。
- 重复处理 guardrail：`docs/progress_closed_gaps.md` 现在负责 do-not-reopen list。只有下一批像已关闭 family 时才打开。
- 下一步 evidence：closeout 期间默认不再新增。只有 `docs/completion_audit.md` 点名具体 defect，或明确 release target 需要剩余 live SkyDiscover catalog gate 时，才重新打开 implementation work。

## Active Queue

| Priority | Batch | Why it is next | Evidence target | Suggested focused checks |
| --- | --- | --- | --- | --- |
| P0 | Post-closeout audit-row decomposition | 只有从 default/local runnable V1 closeout 继续进入 exhaustive release evidence 时才需要。最近的 default/fake-path proof families，包括 storage/audit/object retained relationships、core successful workflow、CLI golden/command-contract completeness、capability/help/payload preflight、source/public experiment direction、runner/adapter direction、host-support policy、lifecycle archive/unarchive/remove 和 home/filesystem/path-registry mapping，已经有 direct evidence，除非有 named gap，否则不要重开。 | 剩余 grouped blueprint/subsystem audit row，而不是宽泛的已证明 family。 | 每次围绕一个 named audit edge 增加窄 tests 或 exact evidence references。 |
| P1 | Remaining live catalog gate | Docker-backed Docker/Harbor/SkyDiscover Docker gates、real Docker capability refresh 和 SkyDiscover Python local-wheel/network/native dependency gates 已在当前 Darwin host 通过。唯一剩余 real-environment gate 是 live SkyDiscover catalog reachability，目前被此环境到 GitHub 的 SSL access 阻塞。 | Live SkyDiscover catalog row。 | 在能访问 GitHub 的网络上重跑 `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 ... pytest -m live_skydiscover_catalog -q -rs`；只有 release host/platform/Python environment 不同时才重跑 Docker/Python opt-in gates。 |

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
