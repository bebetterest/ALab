# ALab 实现 Dashboard

本文是 ALab V1 的短入口 dashboard。它只回答三个问题：项目目前在哪、是否能声称完成、下一步应该读哪个文件。

默认阅读顺序：

1. `docs/progress.md`：只读当前 dashboard。
2. `docs/progress_pipeline.md`：active batch、active queue、full-suite policy 和 update checklist。
3. `docs/completion_audit.md`：requirement-to-evidence matrix 和精确 proof gaps。
4. `docs/progress_closed_gaps.md`：只有 planned batch 可能重复已关闭工作时，才读 do-not-reopen guardrails。
5. `docs/progress_log.md`：只有需要历史上下文时才读 historical journal。

Blueprint 和 subsystem specs 仍是规范性产品契约。

## 当前位置 - 2026-06-03

ALab 已经有覆盖面较广的 runnable V1 implementation，范围包括 local CLI、SQLite home/auth/context foundations、HOME-level agent feedback capture、root-only local read-only dashboard、project/source/experiment lifecycle、local/Docker/Harbor/SkyDiscover runners and adapters、observe/collaboration surfaces、audit、cleanup 和 default contract tests。

当前 active focus 的短摘要：2026-06-02 feedback lifecycle batch 已经落地，并且当前 object-family `services.py` extraction batch 现在已关闭。Auth/root-key/admin-key handlers 位于 `src/alab/credentials.py`；backup/cache prune handlers 位于 `src/alab/maintenance.py`；feedback submit/list/show/archive handlers 位于 `src/alab/feedback.py`；audit list/show handlers 和 audit object-id filtering 位于 `src/alab/audit.py`；dashboard command handler 与 dashboard server/read models 一起位于 `src/alab/dashboard.py`；SkyDiscover catalog add/update/show/remove handlers 以及 catalog/adapter-ref resolution helpers 位于 `src/alab/catalog.py`；annotation add/edit/archive/unarchive/remove 以及 observe annotation list/show handlers 位于 `src/alab/annotations.py`；observe run/artifact/log list/show/export/archive/unarchive/remove handlers 位于 `src/alab/observe.py`；Markdown report export 位于 `src/alab/report.py`；source import/list/show/archive/unarchive/remove handlers 位于 `src/alab/sources.py`；shared trash/removal staging 位于 `src/alab/removal.py`；shared audit-event writing 位于 `src/alab/service_audit.py`；shared request auth gates 位于 `src/alab/service_auth.py`；shared text/reason validation 位于 `src/alab/service_text.py`。这些 CLI surfaces 的 registered behavior 保持不变。Project、experiment、run/submit、context、config 和 tightly coupled lifecycle helpers 会有意继续留在 `src/alab/services.py`，直到其 shared boundaries 能在不制造脆弱 cross-module imports 的情况下移动。大范围一次性 service-module extraction 和新的 runner families 仍不属于本范围。recently closed proof families 由 `docs/progress_closed_gaps.md` 跟踪；除非 `docs/completion_audit.md` 点名新的 concrete edge，或 release target 不同于当前已证明的 host/platform/upstream gates，否则不要重启这些已关闭工作。详细队列状态只放在 `docs/progress_pipeline.md`。

当前 worktree 的 default/local runnable V1 implementation 仍然覆盖面较广，且 default suite 已在 2026-06-04 workspace review 中针对最新 implementation/test changes 重跑。当前 evidence ledger 没有已知缺失实现：

- `docs/completion_audit.md` 已为 feedback file-backed lifecycle edge 更新当前 evidence rows，除 status legend 和 future-state instructions 外，没有已知 active `PARTIAL`、`PENDING` 或 `ENV-GATED` V1 requirement row。
- Latest full default-suite closeout gate 已在 2026-06-04 对 2026-06-03 credentials、maintenance 和 removal helper extraction changes 的 review 中通过。Sandbox full suite 仅因为 dashboard tests 需要绑定 loopback ports 且 managed sandbox 以 `PermissionError` 拒绝而失败；elevated full default suite 已通过。
- Real Docker-backed Docker/Harbor/SkyDiscover Docker behavior、real Docker capability refresh、SkyDiscover Python local-wheel/network/native dependency behavior 和 live SkyDiscover catalog behavior 在当前 Darwin/Docker Desktop worktree 及当前网络上已有 opt-in validation；all-opt-in full suite 的 JUnit 结果为 `tests=390`、`skipped=0`、`failures=0`、`errors=0`。
- Feedback lifecycle batch 的 focused feedback lifecycle、CLI registry/spec/error-code/capability、documentation、dashboard 和 full default-suite checks 已通过；feedback extraction 的 focused feedback/auth/contract checks、`compileall`、docs checks 和 elevated full default suite 已通过；audit extraction 的 focused audit/registry contract checks、import-order checks、`compileall`、docs checks 和 elevated full default suite 已通过；dashboard extraction 的 focused dashboard socket/static/registry contract checks、import-order checks、docs checks 和 elevated full default suite 已通过；catalog extraction 的 focused catalog lifecycle/ref/blocker checks、migration catalog/cache contract checks、full relevant ruff checks、registry-derived CLI contract checks、`compileall` 和 elevated full default suite 已通过；annotation/observe/report/source extraction batch 的 focused annotation/observe/report/source contract 和 smoke checks、full relevant ruff checks、`compileall`、sandbox full-suite dashboard-bind failure confirmation 和 elevated full default suite 已通过；current helper/credentials/maintenance extraction 的 focused removal/trash、auth/key 和 maintenance lifecycle tests、full relevant ruff checks、`compileall`、docs checks、sandbox full-suite dashboard-bind failure confirmation 和 elevated full default suite 已通过。

## Gate 快照

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | 当前 feedback、audit、dashboard、catalog、annotation、observe、report、source、credentials、maintenance service extraction 和 removal helper extraction edges 为 `PASSED` | 只有 changed requirement 或 environment 在 `docs/completion_audit.md` 产生 named evidence gap 时才重开。 |
| Full default suite | `PASSED` | 如果 release claim 前还有额外 implementation/test changes，需要重跑。 |
| CLI contract completeness | focused docs/typed-value checks `PASSED` | 当前 registered CLI surfaces 已由 generated parser/capability/output matrices、docs-derived success schemas、saved result-failure/system-error checks 和 completion-audit consistency guard 证明；commands 或 output variants 变化时重跑/更新。 |
| Non-CLI hardening | Feedback lifecycle no-SQLite/audit checks 和 dashboard focused tests `PASSED` | 仅当 `docs/completion_audit.md` 指出具体 non-CLI edge，或 release target 不同于当前已证明的 host/platform/upstream gates 时才重开。 |
| Real-environment runners | Docker-backed、real Docker capability-refresh、live catalog 与 SkyDiscover Python dependency subsets 在 all-opt-in suite 中 `PASSED` 且 `skipped=0` | 如果 release-target host/platform/Python/network/upstream catalog behavior 变化，重跑 opt-in gates。 |
| Documentation consistency | focused docs/CLI contract checks `PASSED` | Release claim 前重跑更宽的 docs checks。 |

## Do-Not-Reopen 摘要

详细 closed-gap guardrails 放在 `docs/progress_closed_gaps.md`，不放在本 dashboard 或 active queue 中。不要每个 batch 都读它；只有 planned work 像已经关闭的 family 时才打开。

当前高风险已关闭 families 包括 storage/audit/object retained-relationship proof、core successful workflow proof、CLI golden/command-contract completeness、capability/help/payload preflight proof、root-only local dashboard server/API/frontend proof、runtime stack/architecture proof、host-support policy proof、documentation consistency proof、source/public experiment direction proof、runner/adapter direction proof、当前 Darwin real Docker-backed runner 与 capability-refresh validation、当前 live SkyDiscover catalog validation、runtime/layout guards、V1 plaintext/security-boundary negative proof、parser/preflight/output contracts、lifecycle archive/unarchive/remove evidence mapping、context marker conflict/alias 和 context repair pinned-commit/old-path blocker guardrails、credential model 与 credential/token side-effect guardrails、visibility/observe/annotation surfaces、experiment 与 observe-object list filter/sort matrices、service object-family extraction guardrails、public `--from-exp` visibility-intersection behavior、source import canonical tree-hash/remote-Git fidelity、exp-create source-binding/default-source behavior、run/submit lifecycle behavior、public `--source-git` credential-helper warning behavior、explicit token/inspection observe visibility joins、hard-remove blockers、source/validation hard-remove audit/reference relationships、project/experiment retained-row hard-remove relationships、maintenance 和 credential audit metadata、artifact/log/reward capture、project config/schema validation and edit semantics、project init precedence、shared-runner cleanup，以及 Harbor/SkyDiscover catalog/source/evaluator default-path behavior。

## 下一步

当前 worktree 没有 active implementation queue。如果后续还有更多 implementation changes，任何 release-quality claim 前需要再次重跑 full default suite。
