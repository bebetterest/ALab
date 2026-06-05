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

## Current Active Batch - 2026-06-05

- Focus: the requested free evaluation example is closed for the current worktree. `examples/free_evaluation_intro_site/` now demonstrates paired `runner.type = "none"` and `reward.type = "none"` with a no-run manual-review task: completing a Simplified Chinese static introduction site for `모두가 자신의 무가치함과 싸우고 있다`. The example includes a project config, starter site source, content notes, worker prompt, setup/demo scripts, and synchronized English/Chinese README files.
- Explicit non-goals for this batch: do not change free evaluation runtime semantics, submit behavior, report output shape, CLI command contracts, runner families, source import rules, visibility rules, dashboard behavior, or service extraction boundaries. This batch adds runnable example coverage and documentation only.
- Duplicate guardrail: `docs/progress_closed_gaps.md` owns the do-not-reopen list. Open it only if a future batch looks similar to a closed family.
- Evidence added: `bash -n` for the new scripts, `setup_project.sh --dry-run`, `run_demo.sh --dry-run`, a full local setup/demo pass using the repository `.venv` with `validation status: not_required` and submitted `final run id: none`, focused examples/docs contract tests, and `git diff --check`.

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
