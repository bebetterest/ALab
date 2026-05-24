# ALab 实现 Dashboard

本文是 ALab V1 的短入口 dashboard。它只回答三个问题：项目目前在哪、是否能声称完成、下一步应该读哪个文件。

默认阅读顺序：

1. `docs/progress.md`：只读当前 dashboard。
2. `docs/progress_pipeline.md`：active batch、active queue、full-suite policy 和 update checklist。
3. `docs/completion_audit.md`：requirement-to-evidence matrix 和精确 proof gaps。
4. `docs/progress_closed_gaps.md`：只有 planned batch 可能重复已关闭工作时，才读 do-not-reopen guardrails。
5. `docs/progress_log.md`：只有需要历史上下文时才读 historical journal。

Blueprint 和 subsystem specs 仍是规范性产品契约。

## 当前位置 - 2026-05-24

ALab 已经有覆盖面较广的 runnable V1 implementation，范围包括 local CLI、SQLite home/auth/context foundations、HOME-level agent feedback capture、project/source/experiment lifecycle、local/Docker/Harbor/SkyDiscover runners and adapters、observe/collaboration surfaces、audit、cleanup 和 default contract tests。

当前 active focus 的短摘要：2026-05-24 HOME feedback command batch 已经落地，是当前 worktree 的最新 changed edge。它新增了面向所有 initialized-home roles 的顶层 `alab feedback` 提交命令，并把每条 plaintext feedback record 存入 `ALAB_HOME/feedback/`。recently closed proof families 由 `docs/progress_closed_gaps.md` 跟踪；除非 `docs/completion_audit.md` 点名新的 concrete edge，或 release target 不同于当前已证明的 host/platform/upstream gates，否则不要重启这些已关闭工作。详细队列状态只放在 `docs/progress_pipeline.md`。

当前 worktree 的 default/local runnable V1 implementation 已完成 closeout。剩余工作是条件性维护，不是当前 completion blocker：

- `docs/completion_audit.md` 除 status legend 和 future-state instructions 外，已经没有 active `PARTIAL`、`PENDING` 或 `ENV-GATED` V1 requirement row。
- 当前 worktree 的 latest full default-suite closeout gate 在 2026-05-24 HOME feedback command batch 后已经保持 current。
- Real Docker-backed Docker/Harbor/SkyDiscover Docker behavior、real Docker capability refresh、SkyDiscover Python local-wheel/network/native dependency behavior 和 live SkyDiscover catalog behavior 在当前 Darwin/Docker Desktop worktree 及当前网络上已有 opt-in validation；all-opt-in full suite 的 JUnit 结果为 `tests=390`、`skipped=0`、`failures=0`、`errors=0`。
- 最终 README/spec/local-notes/progress/audit consistency pass 在 TSP template usability polish 批次后已有当前 focused evidence；未来 documentation、`.env.example`、`.gitignore` 或 local-note changes 后需要重跑。

## Gate 快照

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | `PASSED` | 只有 changed requirement 或 environment 在 `docs/completion_audit.md` 产生 named evidence gap 时才重开。 |
| Full default suite | `PASSED` | 任何后续 implementation/test change 后，以及任何 release claim 前重跑。 |
| CLI contract completeness | `PASSED` | 当前 registered CLI surfaces 已由 generated parser/capability/output matrices、docs-derived success schemas、saved result-failure/system-error checks 和 completion-audit consistency guard 证明；commands 或 output variants 变化时重跑/更新。 |
| Non-CLI hardening | default/local 与当前 opt-in subsets `PASSED` | 仅当 `docs/completion_audit.md` 指出具体 non-CLI edge，或 release target 不同于当前已证明的 host/platform/upstream gates 时才重开。 |
| Real-environment runners | Docker-backed、real Docker capability-refresh、live catalog 与 SkyDiscover Python dependency subsets 在 all-opt-in suite 中 `PASSED` 且 `skipped=0` | 如果 release-target host/platform/Python/network/upstream catalog behavior 变化，重跑 opt-in gates。 |
| Documentation consistency | `PASSED` | 当前 documentation set 的 focused docs/README/spec/local-notes checks 已通过；未来 documentation、`.env.example`、`.gitignore` 或 local-note changes 后重跑。 |

## Do-Not-Reopen 摘要

详细 closed-gap guardrails 放在 `docs/progress_closed_gaps.md`，不放在本 dashboard 或 active queue 中。不要每个 batch 都读它；只有 planned work 像已经关闭的 family 时才打开。

当前高风险已关闭 families 包括 storage/audit/object retained-relationship proof、core successful workflow proof、CLI golden/command-contract completeness、capability/help/payload preflight proof、runtime stack/architecture proof、host-support policy proof、documentation consistency proof、source/public experiment direction proof、runner/adapter direction proof、当前 Darwin real Docker-backed runner 与 capability-refresh validation、当前 live SkyDiscover catalog validation、runtime/layout guards、V1 plaintext/security-boundary negative proof、parser/preflight/output contracts、lifecycle archive/unarchive/remove evidence mapping、context marker conflict/alias 和 context repair pinned-commit/old-path blocker guardrails、credential model 与 credential/token side-effect guardrails、visibility/observe/annotation surfaces、experiment 与 observe-object list filter/sort matrices、public `--from-exp` visibility-intersection behavior、source import canonical tree-hash/remote-Git fidelity、exp-create source-binding/default-source behavior、run/submit lifecycle behavior、public `--source-git` credential-helper warning behavior、explicit token/inspection observe visibility joins、hard-remove blockers、source/validation hard-remove audit/reference relationships、project/experiment retained-row hard-remove relationships、maintenance 和 credential audit metadata、artifact/log/reward capture、project config/schema validation and edit semantics、project init precedence、shared-runner cleanup，以及 Harbor/SkyDiscover catalog/source/evaluator default-path behavior。

## 下一步

当前没有 implementation batch。未来变更先从 `docs/completion_audit.md` 点名精确新 edge 开始；只有确实产生 active queue 时，才更新 `docs/progress_pipeline.md`。
