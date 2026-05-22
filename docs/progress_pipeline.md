# ALab Implementation Pipeline

This file is the active work queue for ALab V1. Keep `docs/progress.md` as the short dashboard, keep historical details in `docs/progress_log.md`, keep closed proof guardrails in `docs/progress_closed_gaps.md`, and keep requirement evidence in `docs/completion_audit.md`.

## Operating Rules

- Start each batch here, not in the historical log or closed-gap guardrails.
- Before adding work, check the matching audit row in `docs/completion_audit.md`.
- If a planned batch resembles a closed proof family, check `docs/progress_closed_gaps.md` before implementing it.
- Batch related edits and run focused tests for the whole batch, then run broader checks only when the batch meaningfully changes shared behavior.
- Update order after a batch: `docs/completion_audit.md`, this pipeline, `docs/progress_closed_gaps.md` if a reusable guardrail was closed, `docs/progress.md` if gate-level state changed, then `docs/progress_log.md`.
- Keep only the current queue and update policy here. Do not append stale backlog; rewrite or remove queue rows as evidence closes.
- English docs are canonical. Update the synchronized `*_cn.md` file in the same change.

## Current Active Batch - 2026-05-21

- Focus: closeout validation is current after runtime stack/architecture proof, host-support policy proof, documentation consistency proof, run/submit lifecycle proof, lifecycle archive/unarchive/remove evidence mapping, home/filesystem/path-registry evidence mapping, exp-create source-binding/default-source proof, source import canonical tree-hash/remote-Git fidelity proof, project init precedence proof mapping, config edit semantics proof mapping, public `--source-git` credential-helper warning proof, context repair old-path blocker proof, security boundary negative proof, config capability-refresh evidence mapping, shared-runner cleanup, project config/schema proof mapping, project/experiment hard-remove retained-row relationships, source/validation hard-remove audit/reference relationships, maintenance object audit metadata, credential model proof mapping, credential audit metadata, token revoke/regenerate side-effect mapping, context marker conflict/alias mapping, inspection context repair pinned-commit/audit metadata, public `--from-exp` visibility-intersection proof, explicit token/inspection observe visibility joins, run/artifact/log/annotation list filter/sort matrices, experiment list/search filter/sort matrices, and final default-suite gate closed for current default/fake paths.
- Duplicate guardrail: `docs/progress_closed_gaps.md` now owns the do-not-reopen list. Open it only if the next batch looks similar to a closed family.
- Next evidence to add: none by default during closeout. Only reopen implementation work if `docs/completion_audit.md` names a concrete defect or an explicit release target requires an opt-in environment gate.

## Active Queue

| Priority | Batch | Why it is next | Evidence target | Suggested focused checks |
| --- | --- | --- | --- | --- |
| P0 | Post-closeout audit-row decomposition | Only needed if continuing beyond the default/local runnable V1 closeout into exhaustive release evidence. Most recent default/fake-path proof families, including host-support policy, lifecycle archive/unarchive/remove, and home/filesystem/path-registry mapping, already have direct evidence and should not be reopened without a named gap. | Any remaining grouped `PARTIAL` row that names a concrete missing edge, not broad already-proved families. | Add narrow CLI/storage tests around one named audit edge at a time. |
| P1 | Real-environment runner gates | Release-quality validation depends on target machines and services. | Real-environment runner validation rows. | Opt-in tests with `ALAB_RUN_REAL_DOCKER=1` and related SkyDiscover/Harbor environment flags. |

## Guardrail Pointer

Do not keep detailed closed evidence here. Use `docs/progress_closed_gaps.md` only as a duplicate-work guard, and use `docs/completion_audit.md` as the exact evidence source.

When a batch closes a gap that future agents are likely to repeat, add the concise closed family to `docs/progress_closed_gaps.md` and keep the audit row's direct evidence current.

## Full-Suite Policy

The full default suite is intentionally not run after every small edit. Run it when one of these is true:

- A batch changes shared command dispatch, storage schema, runner services, visibility logic, lifecycle semantics, or renderer behavior.
- A focused batch closes multiple audit rows and the next step is a completion or release-quality claim.
- The user explicitly asks for a full verification pass.

Until then, record focused verification in the progress log. If implementation/test changes occur after the latest full-suite pass, mark the full-suite gate stale again.

## Update Checklist

1. Update the relevant `docs/completion_audit.md` row with exact evidence and remaining action.
2. Remove or rewrite the corresponding active queue item if the gap is closed.
3. Add a concise guardrail to `docs/progress_closed_gaps.md` if future agents are likely to repeat the closed proof family.
4. Update `docs/progress.md` only if a gate state, top-level blocker, or active focus changed.
5. Append a concise dated entry to `docs/progress_log.md`.
6. Synchronize every changed English doc with its `*_cn.md` counterpart.
