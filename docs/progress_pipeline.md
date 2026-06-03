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

## Current Active Batch - 2026-06-03

- Focus: the fourth object-family `services.py` extraction is closed for the current worktree. SkyDiscover catalog add/update/show/remove handlers and catalog/adapter-ref resolution helpers now live in `src/alab/catalog.py`; shared audit-event writing lives in `src/alab/service_audit.py`; the dashboard command handler remains in `src/alab/dashboard.py`; audit list/show handlers and audit object-id filtering remain in `src/alab/audit.py`; feedback handlers remain in `src/alab/feedback.py`; shared request auth gates remain in `src/alab/service_auth.py`; and shared text/reason validation remains in `src/alab/service_text.py`. Registered catalog, dashboard, audit, and feedback CLI behavior remains unchanged.
- Explicit non-goals for this batch: do not continue into broad all-at-once object-family extraction, do not change SkyDiscover catalog add/update/show/remove behavior, catalog checkout/ref resolution semantics, adapter-derived source behavior, runner config validation, dashboard server routes, read models, loopback/token behavior, static assets, audit command authorization, filters, output fields, JSON sanitization, audit persistence, feedback deletion, SQLite feedback rows, feedback archive audit rows, project-admin scoped feedback reads, JSON CLI output, hosted/remote dashboard behavior, or new runner families.
- Duplicate guardrail: `docs/progress_closed_gaps.md` owns the do-not-reopen list. Open it only if a future batch looks similar to a closed family.
- Evidence added: focused SkyDiscover catalog lifecycle/ref/blocker checks, migration catalog/cache metadata contract checks, registry-derived CLI registry/spec/option/static contract checks, full relevant ruff checks, `compileall`, sandbox full default suite failure limited to dashboard loopback bind `PermissionError`, and elevated full default suite pass.

## Active Queue

No active queue remains for the current worktree.

Future queue rows must name a specific changed requirement, command, option, invariant, warning/error code, lifecycle rule, visibility rule, runner contract, persistence contract, release-target environment, or upstream catalog behavior before implementation starts.

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
