# ALab Implementation Dashboard

This file is the short entry dashboard for ALab V1. It answers only three questions: where the project stands, whether completion can be claimed, and which file to read next.

Default read order:

1. `docs/progress.md`: current dashboard only.
2. `docs/progress_pipeline.md`: active batch, active queue, full-suite policy, and update checklist.
3. `docs/completion_audit.md`: requirement-to-evidence matrix and exact proof gaps.
4. `docs/progress_closed_gaps.md`: do-not-reopen guardrails only when a planned batch might duplicate closed work.
5. `docs/progress_log.md`: historical journal only when older context is needed.

The blueprint and subsystem specs remain the normative product contract.

## Current Position - 2026-06-03

ALab has a broad runnable V1 implementation across the local CLI, SQLite home/auth/context foundations, HOME-level agent feedback capture, root-only local read-only dashboard, project/source/experiment lifecycle, local/Docker/Harbor/SkyDiscover runners and adapters, observe/collaboration surfaces, audit, cleanup, and default contract tests.

Current active focus, in summary only: the 2026-06-02 feedback lifecycle batch has landed, and the first four object-family `services.py` extractions are now closed. Feedback submit/list/show/archive handlers live in `src/alab/feedback.py`; audit list/show handlers and audit object-id filtering live in `src/alab/audit.py`; the dashboard command handler lives with the dashboard server/read models in `src/alab/dashboard.py`; SkyDiscover catalog add/update/show/remove handlers and catalog/adapter-ref resolution helpers live in `src/alab/catalog.py`; shared audit-event writing lives in `src/alab/service_audit.py`; shared request auth gates live in `src/alab/service_auth.py`; and shared text/reason validation lives in `src/alab/service_text.py`. Registered feedback, audit, dashboard, and catalog CLI behavior remains unchanged. Feedback deletion, project-admin feedback reads, JSON CLI output, hosted/remote dashboard behavior, SkyDiscover catalog behavior changes, broad all-at-once service-module extraction, and new runner families remain out of scope. Recently closed proof families are tracked in `docs/progress_closed_gaps.md`; do not restart them unless `docs/completion_audit.md` names a new concrete edge or the release target differs from the currently proved host/platform/upstream gates. The detailed queue state lives in `docs/progress_pipeline.md`.

The default/local runnable V1 implementation remains broad, and the default suite has been rerun after the latest 2026-06-03 implementation/test changes. There is no known missing implementation in the current evidence ledger:

- `docs/completion_audit.md` has current evidence rows for the feedback file-backed lifecycle edge and no known active `PARTIAL`, `PENDING`, or `ENV-GATED` V1 requirement row outside the status legend and future-state instructions.
- The latest full default-suite closeout gate passed after the 2026-06-03 catalog service extraction changes. The sandbox full suite failed only because dashboard tests bind loopback ports that the managed sandbox rejected with `PermissionError`; the elevated full default suite passed.
- Real Docker-backed Docker/Harbor/SkyDiscover Docker behavior, real Docker capability refresh, SkyDiscover Python local-wheel/network/native dependency behavior, and live SkyDiscover catalog behavior have current opt-in validation on this Darwin/Docker Desktop worktree and current network; the all-opt-in full suite passed with JUnit `tests=390`, `skipped=0`, `failures=0`, and `errors=0`.
- Focused feedback lifecycle, auth re-export, CLI registry/spec/option/static contract, documentation, dashboard, and full default-suite checks passed for the feedback lifecycle batch; focused feedback/auth/contract checks, `compileall`, docs checks, and elevated full default suite passed for the feedback extraction; focused audit/registry contract checks, import-order checks, `compileall`, docs checks, and elevated full default suite passed for the audit extraction; focused dashboard socket/static/registry contract checks, import-order checks, docs checks, and elevated full default suite passed for the dashboard extraction; focused catalog lifecycle/ref/blocker checks, migration catalog/cache contract checks, full relevant ruff checks, registry-derived CLI contract checks, `compileall`, and elevated full default suite passed for the catalog extraction.

## Gate Snapshot

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | `PASSED` for the current feedback, audit, dashboard, and catalog service extraction edges | Reopen only when a changed requirement or environment creates a named evidence gap in `docs/completion_audit.md`. |
| Full default suite | `PASSED` | Re-run if additional implementation/test changes land before a release claim. |
| CLI contract completeness | focused docs/typed-value checks `PASSED` | Current registered CLI surfaces are proved by generated parser/capability/output matrices, docs-derived success schemas, saved result-failure/system-error checks, and the completion-audit consistency guard; rerun/update when commands or output variants change. |
| Non-CLI hardening | Feedback lifecycle no-SQLite/audit checks and dashboard focused tests `PASSED` | Reopen only if `docs/completion_audit.md` names a concrete non-CLI edge or a release target differs from the currently proved host/platform/upstream gates. |
| Real-environment runners | Docker-backed, real Docker capability-refresh, live catalog, and SkyDiscover Python dependency subsets `PASSED` with `skipped=0` in the all-opt-in suite | Re-run opt-in gates on release-target hosts if host/platform/Python/network/upstream catalog behavior changes. |
| Documentation consistency | focused docs/CLI contract checks `PASSED` | Rerun broader docs checks before a release claim. |

## Do-Not-Reopen Summary

Detailed closed-gap guardrails live in `docs/progress_closed_gaps.md`, not in this dashboard or the active queue. Do not read that file on every batch; open it only when the planned work resembles a previously closed family.

Current high-risk closed families include storage/audit/object retained-relationship proof, core successful workflow proof, CLI golden/command-contract completeness, capability/help/payload preflight proof, root-only local dashboard server/API/frontend proof, runtime stack/architecture proof, host-support policy proof, documentation consistency proof, source/public experiment direction proof, runner/adapter direction proof, current Darwin real Docker-backed runner and capability-refresh validation, current live SkyDiscover catalog validation, runtime/layout guards, V1 plaintext/security-boundary negative proof, parser/preflight/output contracts, lifecycle archive/unarchive/remove evidence mapping, context marker conflict/alias and context repair pinned-commit/old-path blocker guardrails, credential model and credential/token side-effect guardrails, visibility/observe/annotation surfaces, experiment and observe-object list filter/sort matrices, public `--from-exp` visibility-intersection behavior, source import canonical tree-hash/remote-Git fidelity, exp-create source-binding/default-source behavior, run/submit lifecycle behavior, public `--source-git` credential-helper warning behavior, explicit token/inspection observe visibility joins, hard-remove blockers, source/validation hard-remove audit/reference relationships, project/experiment retained-row hard-remove relationships, maintenance and credential audit metadata, artifact/log/reward capture, project config/schema validation and edit semantics, project init precedence, shared-runner cleanup, and Harbor/SkyDiscover catalog/source/evaluator default-path behavior.

## Next Step

No active implementation queue remains for this worktree. Run the full default suite before any release-quality claim.
