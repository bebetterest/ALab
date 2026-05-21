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

Current active focus, in summary only: the recently closed proof families are tracked in `docs/progress_closed_gaps.md`, and the remaining active queue is grouped audit-row decomposition plus release gates. Do not restart closed work such as documentation consistency proof, security boundary negative proof, source import canonical tree-hash/remote-Git fidelity proof, exp-create source-binding/default-source proof, run/submit lifecycle proof, public `--source-git` credential-helper warning proof, context repair old-path blocker proof, config edit semantics proof mapping, project init precedence proof mapping, shared-runner cleanup, project config/schema mapping, hard-remove retained-row relationships, credential model proof mapping, maintenance/credential/token/context audit metadata, context marker conflict/alias mapping, observe visibility/filter/sort matrices, or public `--from-exp` visibility-intersection proof unless `docs/completion_audit.md` names a new edge. The detailed queue lives in `docs/progress_pipeline.md`.

The default/local runnable V1 implementation is in closeout for this worktree. Remaining items are release/evidence hardening, not missing runnable core:

- Remaining grouped or `PARTIAL` rows in `docs/completion_audit.md` still need direct evidence, focused tests, or explicit `ENV-GATED` scoping.
- The full default-suite closeout gate passed on the current worktree after the source-import/tree-hash, public Git helper-proof, and documentation closeout batches.
- Real Docker/network/service behavior remains opt-in release validation.
- The final README/spec/local-notes/progress/audit consistency pass has current focused evidence; rerun it after future documentation, `.env.example`, `.gitignore`, or local-note changes.

## Gate Snapshot

| Gate | State | Completion blocker |
| --- | --- | --- |
| Requirement evidence | `PARTIAL` | Convert remaining grouped or `PARTIAL` audit rows into direct proof, one focused batch at a time. |
| Full default suite | `PASSED` | Re-run `uv run pytest -q`, `uv run ruff check`, `python3 -m compileall -q src tests`, and `git diff --check` if any further implementation/test changes occur before a completion or release claim. |
| CLI contract completeness | `PARTIAL` | The command-error matrix is proved for current runtime surfaces; remaining CLI work is long-tail command-specific rendering plus future context variants named in `docs/completion_audit.md`. |
| Non-CLI hardening | `PARTIAL` | Finish object relationship invariants and remaining collaboration hardening. |
| Real-environment runners | `ENV-GATED` | Re-run opt-in Docker/Harbor/SkyDiscover gates on machines with required services, images, and network. |
| Documentation consistency | `PASSED` | Focused docs/README/spec/local-notes checks passed for the current documentation set; rerun after future documentation, `.env.example`, `.gitignore`, or local-note changes. |

## Do-Not-Reopen Summary

Detailed closed-gap guardrails live in `docs/progress_closed_gaps.md`, not in this dashboard or the active queue. Do not read that file on every batch; open it only when the planned work resembles a previously closed family.

Current high-risk closed families include documentation consistency proof, runtime/layout guards, V1 plaintext/security-boundary negative proof, parser/preflight/output contracts, context marker conflict/alias and context repair pinned-commit/old-path blocker guardrails, credential model and credential/token side-effect guardrails, visibility/observe/annotation surfaces, experiment and observe-object list filter/sort matrices, public `--from-exp` visibility-intersection behavior, source import canonical tree-hash/remote-Git fidelity, exp-create source-binding/default-source behavior, run/submit lifecycle behavior, public `--source-git` credential-helper warning behavior, explicit token/inspection observe visibility joins, hard-remove blockers, source/validation hard-remove audit/reference relationships, project/experiment retained-row hard-remove relationships, maintenance and credential audit metadata, artifact/log/reward capture, project config/schema validation and edit semantics, project init precedence, shared-runner cleanup, and Harbor/SkyDiscover catalog/source/evaluator default-path behavior.

## Next Step

Use the current active batch at the top of `docs/progress_pipeline.md` for the next implementation batch. Update that focus whenever it changes; this dashboard should stay short and only record gate-level state changes.
