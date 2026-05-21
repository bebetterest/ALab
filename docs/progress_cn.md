# ALab 实现 Dashboard

本文是 ALab V1 的短入口 dashboard。它只回答三个问题：项目目前在哪、是否能声称完成、下一步应该读哪个文件。

默认阅读顺序：

1. `docs/progress.md`：只读当前 dashboard。
2. `docs/progress_pipeline.md`：active batch、active queue、full-suite policy 和 update checklist。
3. `docs/completion_audit.md`：requirement-to-evidence matrix 和精确 proof gaps。
4. `docs/progress_closed_gaps.md`：只有 planned batch 可能重复已关闭工作时，才读 do-not-reopen guardrails。
5. `docs/progress_log.md`：只有需要历史上下文时才读 historical journal。

Blueprint 和 subsystem specs 仍是规范性产品契约。

## 当前位置 - 2026-05-21

ALab 已经有覆盖面较广的 runnable V1 implementation，范围包括 local CLI、SQLite home/auth/context foundations、project/source/experiment lifecycle、local/Docker/Harbor/SkyDiscover runners and adapters、observe/collaboration surfaces、audit、cleanup 和 default contract tests。

当前 active focus 的短摘要：recently closed proof families 由 `docs/progress_closed_gaps.md` 跟踪，剩余 active queue 是 grouped audit-row decomposition 加 release gates。除非 `docs/completion_audit.md` 点名新的 edge，不要重启 shared-runner cleanup、project config/schema mapping、hard-remove retained-row relationships、credential model proof mapping、maintenance/credential/token/context audit metadata、context marker conflict/alias mapping、observe visibility/filter/sort matrices 或 public `--from-exp` visibility-intersection proof 等已关闭工作。详细队列只放在 `docs/progress_pipeline.md`。

Goal 还不能声称完成。目前 blocker 是证据和 release gates，而不是缺少 first runnable product：

- `docs/completion_audit.md` 中剩余 grouped 或 `PARTIAL` rows 仍需要 direct evidence、focused tests，或明确的 `ENV-GATED` scope。
- 当前 worktree 的 full default-suite gate 已 stale。
- Real Docker/network/service behavior 仍属于 opt-in release validation。
- Implementation 停止变化后，还需要做最终 README/spec/AGENTS/progress/audit consistency pass。

## Gate 快照

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | `PARTIAL` | 将剩余 grouped 或 `PARTIAL` audit rows 按 batch 转成直接证明。 |
| Full default suite | `STALE` | 在任何 completion claim 前，必须在当前 worktree 重新运行 `uv run pytest -q`、`uv run ruff check`、`python3 -m compileall -q src tests` 和 `git diff --check`。 |
| CLI contract completeness | `PARTIAL` | 当前 runtime surfaces 的 command-error matrix 已证明；剩余 CLI work 是 long-tail command-specific rendering，以及 `docs/completion_audit.md` 点名的 future context variants。 |
| Non-CLI hardening | `PARTIAL` | 完成 object relationship invariants 和剩余 collaboration hardening。 |
| Real-environment runners | `ENV-GATED` | 在具备 required services、images 和 network 的机器上重跑 opt-in Docker/Harbor/SkyDiscover gates。 |
| Documentation consistency | `PARTIAL` | Implementation queue 稳定后，对 README、AGENTS、specs、dashboard、pipeline、guardrails、log 和 audit 做最终一致性检查。 |

## Do-Not-Reopen 摘要

详细 closed-gap guardrails 放在 `docs/progress_closed_gaps.md`，不放在本 dashboard 或 active queue 中。不要每个 batch 都读它；只有 planned work 像已经关闭的 family 时才打开。

当前高风险已关闭 families 包括 runtime/layout guards、parser/preflight/output contracts、context marker conflict/alias 和 context repair pinned-commit guardrails、credential model 与 credential/token side-effect guardrails、visibility/observe/annotation surfaces、experiment 与 observe-object list filter/sort matrices、public `--from-exp` visibility-intersection behavior、explicit token/inspection observe visibility joins、hard-remove blockers、source/validation hard-remove audit/reference relationships、project/experiment retained-row hard-remove relationships、maintenance 和 credential audit metadata、artifact/log/reward capture、project config/schema validation、shared-runner cleanup，以及 Harbor/SkyDiscover catalog/source/evaluator default-path behavior。

## 下一步

使用 `docs/progress_pipeline.md` 顶部的 current active batch 选择下一批 implementation。Active focus 变化时先更新该焦点；本 dashboard 只保留 gate-level state changes，保持短小。
