# ALab Documentation Guide

This directory contains ALab's V1 product contract, subsystem specifications, evidence ledger, progress queue, historical log, and synchronized Chinese translations. English documents are canonical; update the matching `*_cn.md` document in the same change whenever an English document changes.

## Default Reading Order

1. [progress.md](progress.md): start here for the current project state, gate snapshot, and next-step pointer.
2. [progress_pipeline.md](progress_pipeline.md): read this before starting work; it owns the active batch, active queue, full-suite policy, and update checklist.
3. [completion_audit.md](completion_audit.md): use this to identify exact requirement evidence and any concrete proof gap.
4. [progress_closed_gaps.md](progress_closed_gaps.md): open this only when planned work resembles a previously closed proof family.
5. [progress_log.md](progress_log.md): use this only for historical context or to trace when a decision, implementation batch, or validation run happened.
6. [blueprint.md](blueprint.md) and the `spec_*.md` files: use these when changing product behavior, command contracts, storage, lifecycle semantics, runners, observe behavior, or tests.

## Document Groups

| Group | Files | Purpose |
| --- | --- | --- |
| Product overview | [blueprint.md](blueprint.md), [blueprint_cn.md](blueprint_cn.md) | Canonical V1 overview: product definition, boundaries, runtime stack, home layout, CLI direction, source/experiment direction, runner/adapter direction, milestones, and references. |
| CLI contract | [spec_cli.md](spec_cli.md), [spec_cli_cn.md](spec_cli_cn.md) | Invocation model, output format, debug behavior, errors, exit codes, command groups, aliases, and per-command contracts. |
| Storage/auth/context contract | [spec_storage_auth_context.md](spec_storage_auth_context.md), [spec_storage_auth_context_cn.md](spec_storage_auth_context_cn.md) | Home layout, SQLite rules, DDL schema, JSON field contracts, credentials, secrets, global config, project config persistence, context markers, migrations, and backup. |
| Project/source/experiment contract | [spec_project_source_experiment.md](spec_project_source_experiment.md), [spec_project_source_experiment_cn.md](spec_project_source_experiment_cn.md) | Project config schema, project init, source model, experiment lifecycle, worktree maintenance, mutable scope, run lifecycle, and submit lifecycle. |
| Lifecycle contract | [spec_lifecycle.md](spec_lifecycle.md), [spec_lifecycle_cn.md](spec_lifecycle_cn.md) | Archive, unarchive, hard remove, restore, repair, revoke, prune, lifecycle blockers, trash staging, and lifecycle audit visibility. |
| Runner/adapter contract | [spec_runners_adapters.md](spec_runners_adapters.md), [spec_runners_adapters_cn.md](spec_runners_adapters_cn.md) | Runner contract, runtime directories, environment injection, local runner, Docker runner, rewards, artifacts, logs, hidden assets, Harbor, SkyDiscover, and Docker-unavailable behavior. |
| Observe/collaboration contract | [spec_observe_collaboration.md](spec_observe_collaboration.md), [spec_observe_collaboration_cn.md](spec_observe_collaboration_cn.md) | Visibility model, observe commands, search/pagination/sorting, filters, best ranking, logs, artifact export, tags, annotations, and public safe status. |
| Verification contract | [spec_tests.md](spec_tests.md), [spec_tests_cn.md](spec_tests_cn.md) | Test strategy and acceptance gates for CLI, storage, auth/context/lifecycle, project/source, run/submit, runner/reward/log/artifact, adapters, and observe/collaboration. |
| Current progress | [progress.md](progress.md), [progress_cn.md](progress_cn.md) | Short dashboard for current state, completion gates, do-not-reopen summary, and next step. |
| Active work queue | [progress_pipeline.md](progress_pipeline.md), [progress_pipeline_cn.md](progress_pipeline_cn.md) | Active batch and queue. Keep this narrow; do not append stale backlog. |
| Evidence ledger | [completion_audit.md](completion_audit.md), [completion_audit_cn.md](completion_audit_cn.md) | Requirement-to-evidence matrix used to decide whether V1 completion can be claimed. |
| Closed-gap guardrails | [progress_closed_gaps.md](progress_closed_gaps.md), [progress_closed_gaps_cn.md](progress_closed_gaps_cn.md) | Duplicate-work guardrails for proof families that are already closed. |
| Historical journal | [progress_log.md](progress_log.md), [progress_log_cn.md](progress_log_cn.md) | Chronological implementation and validation history. Use for traceability, not as the current queue. |
| Assets | [assets/readme-header.png](assets/readme-header.png) | README visual asset. |

## Update Rules

- Treat [blueprint.md](blueprint.md) and the subsystem specs as the normative product contract.
- Treat [completion_audit.md](completion_audit.md) as the source of truth for requirement evidence.
- Treat [progress_pipeline.md](progress_pipeline.md) as the only active queue.
- Treat [progress_closed_gaps.md](progress_closed_gaps.md) as a duplicate-work guard, not a backlog.
- Treat [progress_log.md](progress_log.md) as historical evidence, not current status.
- When a requirement, command, warning/error code, lifecycle rule, visibility rule, runner contract, storage contract, release target, or upstream catalog behavior changes, update the relevant spec first, then the audit/progress files.
- Keep English and Chinese document pairs synchronized in the same change.
