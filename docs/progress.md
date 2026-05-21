# ALab Implementation Dashboard

This file is the short entry dashboard for ALab V1. It answers only three questions: where the project stands, whether completion can be claimed, and which file to read next.

Default read order:

1. `docs/progress.md`: current dashboard only.
2. `docs/progress_pipeline.md`: active batch, active queue, full-suite policy, and update checklist.
3. `docs/completion_audit.md`: requirement-to-evidence matrix and exact proof gaps.
4. `docs/progress_closed_gaps.md`: do-not-reopen guardrails only when a planned batch might duplicate closed work.
5. `docs/progress_log.md`: historical journal only when older context is needed.

The blueprint and subsystem specs remain the normative product contract.

## Current Position - 2026-05-21

ALab has a broad runnable V1 implementation across the local CLI, SQLite home/auth/context foundations, project/source/experiment lifecycle, local/Docker/Harbor/SkyDiscover runners and adapters, observe/collaboration surfaces, audit, cleanup, and default contract tests.

Current active focus, in summary only: the recently closed proof families are tracked in `docs/progress_closed_gaps.md`, and the remaining active queue is grouped audit-row decomposition plus release gates. Do not restart closed work such as shared-runner cleanup, project config/schema mapping, hard-remove retained-row relationships, credential model proof mapping, maintenance/credential/token/context audit metadata, context marker conflict/alias mapping, observe visibility/filter/sort matrices, or public `--from-exp` visibility-intersection proof unless `docs/completion_audit.md` names a new edge. The detailed queue lives in `docs/progress_pipeline.md`.

The goal is not complete yet. The blockers are evidence and release gates, not lack of a first runnable product:

- Remaining grouped or `PARTIAL` rows in `docs/completion_audit.md` still need direct evidence, focused tests, or explicit `ENV-GATED` scoping.
- The full default-suite gate is stale for the current worktree.
- Real Docker/network/service behavior remains opt-in release validation.
- Final README/spec/AGENTS/progress/audit consistency still needs to run after implementation stops changing.

## Gate Snapshot

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | `PARTIAL` | Convert remaining grouped or `PARTIAL` audit rows into direct proof, one focused batch at a time. |
| Full default suite | `STALE` | Re-run `uv run pytest -q`, `uv run ruff check`, `python3 -m compileall -q src tests`, and `git diff --check` on the current worktree before any completion claim. |
| CLI contract completeness | `PARTIAL` | The command-error matrix is proved for current runtime surfaces; remaining CLI work is long-tail command-specific rendering plus future context variants named in `docs/completion_audit.md`. |
| Non-CLI hardening | `PARTIAL` | Finish object relationship invariants and remaining collaboration hardening. |
| Real-environment runners | `ENV-GATED` | Re-run opt-in Docker/Harbor/SkyDiscover gates on machines with required services, images, and network. |
| Documentation consistency | `PARTIAL` | Final pass across README, AGENTS, specs, dashboard, pipeline, guardrails, log, and audit after the implementation queue stabilizes. |

## Do-Not-Reopen Summary

Detailed closed-gap guardrails live in `docs/progress_closed_gaps.md`, not in this dashboard or the active queue. Do not read that file on every batch; open it only when the planned work resembles a previously closed family.

Current high-risk closed families include runtime/layout guards, parser/preflight/output contracts, context marker conflict/alias and context repair pinned-commit guardrails, credential model and credential/token side-effect guardrails, visibility/observe/annotation surfaces, experiment and observe-object list filter/sort matrices, public `--from-exp` visibility-intersection behavior, explicit token/inspection observe visibility joins, hard-remove blockers, source/validation hard-remove audit/reference relationships, project/experiment retained-row hard-remove relationships, maintenance and credential audit metadata, artifact/log/reward capture, project config/schema validation, shared-runner cleanup, and Harbor/SkyDiscover catalog/source/evaluator default-path behavior.

## Next Step

Use the current active batch at the top of `docs/progress_pipeline.md` for the next implementation batch. Update that focus whenever it changes; this dashboard should stay short and only record gate-level state changes.
