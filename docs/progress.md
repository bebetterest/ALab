# ALab Implementation Dashboard

This file is the short entry dashboard for ALab V1. It answers only three questions: where the project stands, whether completion can be claimed, and which file to read next.

Default read order:

1. `docs/progress.md`: current dashboard only.
2. `docs/progress_pipeline.md`: active batch, active queue, full-suite policy, and update checklist.
3. `docs/completion_audit.md`: requirement-to-evidence matrix and exact proof gaps.
4. `docs/progress_closed_gaps.md`: do-not-reopen guardrails only when a planned batch might duplicate closed work.
5. `docs/progress_log.md`: historical journal only when older context is needed.

The blueprint and subsystem specs remain the normative product contract.

## Current Position - 2026-05-23

ALab has a broad runnable V1 implementation across the local CLI, SQLite home/auth/context foundations, project/source/experiment lifecycle, local/Docker/Harbor/SkyDiscover runners and adapters, observe/collaboration surfaces, audit, cleanup, and default contract tests.

Current active focus, in summary only: there is no open implementation or evidence queue for the current worktree. Recently closed proof families are tracked in `docs/progress_closed_gaps.md`; do not restart them unless `docs/completion_audit.md` names a new concrete edge or the release target differs from the currently proved host/platform/upstream gates. The detailed queue state lives in `docs/progress_pipeline.md`.

The default/local runnable V1 implementation is closed for this worktree. Remaining work is conditional maintenance, not a current completion blocker:

- `docs/completion_audit.md` has no active `PARTIAL`, `PENDING`, or `ENV-GATED` V1 requirement row outside the status legend and future-state instructions.
- The latest full default-suite closeout gate is current for this worktree after the 2026-05-23 TSP template library batch.
- Real Docker-backed Docker/Harbor/SkyDiscover Docker behavior, real Docker capability refresh, SkyDiscover Python local-wheel/network/native dependency behavior, and live SkyDiscover catalog behavior have current opt-in validation on this Darwin/Docker Desktop worktree and current network; the all-opt-in full suite passed with JUnit `tests=389`, `skipped=0`, `failures=0`, and `errors=0`.
- The final README/spec/local-notes/progress/audit consistency pass has current focused evidence; rerun it after future documentation, `.env.example`, `.gitignore`, or local-note changes.

## Gate Snapshot

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | `PASSED` | Reopen only when a changed requirement or environment creates a named evidence gap in `docs/completion_audit.md`. |
| Full default suite | `PASSED` | Re-run after any later implementation/test change and before any release claim. |
| CLI contract completeness | `PASSED` | Current registered CLI surfaces are proved by generated parser/capability/output matrices, docs-derived success schemas, saved result-failure/system-error checks, and the completion-audit consistency guard; rerun/update when commands or output variants change. |
| Non-CLI hardening | default/local and current opt-in subsets `PASSED` | Reopen only if `docs/completion_audit.md` names a concrete non-CLI edge or a release target differs from the currently proved host/platform/upstream gates. |
| Real-environment runners | Docker-backed, real Docker capability-refresh, live catalog, and SkyDiscover Python dependency subsets `PASSED` with `skipped=0` in the all-opt-in suite | Re-run opt-in gates on release-target hosts if host/platform/Python/network/upstream catalog behavior changes. |
| Documentation consistency | `PASSED` | Focused docs/README/spec/local-notes checks passed for the current documentation set; rerun after future documentation, `.env.example`, `.gitignore`, or local-note changes. |

## Do-Not-Reopen Summary

Detailed closed-gap guardrails live in `docs/progress_closed_gaps.md`, not in this dashboard or the active queue. Do not read that file on every batch; open it only when the planned work resembles a previously closed family.

Current high-risk closed families include storage/audit/object retained-relationship proof, core successful workflow proof, CLI golden/command-contract completeness, capability/help/payload preflight proof, runtime stack/architecture proof, host-support policy proof, documentation consistency proof, source/public experiment direction proof, runner/adapter direction proof, current Darwin real Docker-backed runner and capability-refresh validation, current live SkyDiscover catalog validation, runtime/layout guards, V1 plaintext/security-boundary negative proof, parser/preflight/output contracts, lifecycle archive/unarchive/remove evidence mapping, context marker conflict/alias and context repair pinned-commit/old-path blocker guardrails, credential model and credential/token side-effect guardrails, visibility/observe/annotation surfaces, experiment and observe-object list filter/sort matrices, public `--from-exp` visibility-intersection behavior, source import canonical tree-hash/remote-Git fidelity, exp-create source-binding/default-source behavior, run/submit lifecycle behavior, public `--source-git` credential-helper warning behavior, explicit token/inspection observe visibility joins, hard-remove blockers, source/validation hard-remove audit/reference relationships, project/experiment retained-row hard-remove relationships, maintenance and credential audit metadata, artifact/log/reward capture, project config/schema validation and edit semantics, project init precedence, shared-runner cleanup, and Harbor/SkyDiscover catalog/source/evaluator default-path behavior.

## Next Step

There is no current implementation batch. For future changes, start at `docs/completion_audit.md` to name the exact new edge, then update `docs/progress_pipeline.md` only if a real active queue is created.
