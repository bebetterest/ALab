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

- Focus: grouped audit-row decomposition after shared-runner cleanup, project config/schema proof mapping, project/experiment hard-remove retained-row relationships, source/validation hard-remove audit/reference relationships, maintenance object audit metadata, credential model proof mapping, credential audit metadata, token revoke/regenerate side-effect mapping, context marker conflict/alias mapping, inspection context repair pinned-commit/audit metadata, public `--from-exp` visibility-intersection proof, explicit token/inspection observe visibility joins, run/artifact/log/annotation list filter/sort matrices, and experiment list/search filter/sort matrices closed for current default/fake paths.
- Duplicate guardrail: `docs/progress_closed_gaps.md` now owns the do-not-reopen list. Open it only if the next batch looks similar to a closed family.
- Next evidence to add: the next grouped audit row that can be converted into direct proof.

## Active Queue

| Priority | Batch | Why it is next | Evidence target | Suggested focused checks |
| --- | --- | --- | --- | --- |
| P0 | Grouped audit-row decomposition | Observe filter/sort matrices, credential model evidence, credential/token side-effect evidence, context marker conflict/alias mapping, and inspection context repair pinned-commit metadata now have direct default-path evidence; the remaining evidence work is grouped audit rows that still need final decomposition across current object families and future surfaces. | Storage/auth/context audit rows plus any remaining grouped lifecycle evidence rows. | Add narrow CLI/storage tests around one grouped audit row at a time, continuing with the object family that still has the weakest direct proof. |
| P0 | Full default-suite gate | Cannot claim completion while stale. | P0 gate in `docs/completion_audit.md` and gate snapshot in `docs/progress.md`. | Run only after the next code/test batch or immediately before a completion claim. |
| P1 | Real-environment runner gates | Release-quality validation depends on target machines and services. | Real-environment runner validation rows. | Opt-in tests with `ALAB_RUN_REAL_DOCKER=1` and related SkyDiscover/Harbor environment flags. |
| P1 | Final docs consistency pass | Docs should be checked after implementation stabilizes, not after every small proof batch. | Documentation consistency rows. | Markdown pair check, README tree sync, CLI spec sync, and manual pass across README/AGENTS/specs/audit/progress. |

## Guardrail Pointer

Do not keep detailed closed evidence here. Use `docs/progress_closed_gaps.md` only as a duplicate-work guard, and use `docs/completion_audit.md` as the exact evidence source.

When a batch closes a gap that future agents are likely to repeat, add the concise closed family to `docs/progress_closed_gaps.md` and keep the audit row's direct evidence current.

## Full-Suite Policy

The full default suite is intentionally not run after every small edit. Run it when one of these is true:

- A batch changes shared command dispatch, storage schema, runner services, visibility logic, lifecycle semantics, or renderer behavior.
- A focused batch closes multiple audit rows and the next step is a completion or release-quality claim.
- The user explicitly asks for a full verification pass.

Until then, record focused verification in the progress log and keep the full-suite gate marked stale.

## Update Checklist

1. Update the relevant `docs/completion_audit.md` row with exact evidence and remaining action.
2. Remove or rewrite the corresponding active queue item if the gap is closed.
3. Add a concise guardrail to `docs/progress_closed_gaps.md` if future agents are likely to repeat the closed proof family.
4. Update `docs/progress.md` only if a gate state, top-level blocker, or active focus changed.
5. Append a concise dated entry to `docs/progress_log.md`.
6. Synchronize every changed English doc with its `*_cn.md` counterpart.
