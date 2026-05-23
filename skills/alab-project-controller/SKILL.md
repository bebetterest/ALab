---
name: alab-project-controller
description: Use when managing one existing ALab project with a project admin key to create and coordinate experiments, validate and adjust project configuration, manage project-scoped source or lifecycle state, and launch worker agents without exposing admin credentials.
---

# ALab Project Controller

## Overview

Use this skill when Codex coordinates one ALab project with a project admin key. The controller creates experiments, launches worker agents in worktrees, observes project-visible evidence, compares best runs, and manages project-scoped configuration and lifecycle operations.

This skill is not a global administrator. It must not initialize ALab homes, rotate root credentials, manage SkyDiscover catalogs, prune global caches/backups, or create/revoke project admin keys.

## Credential Rules

- Accept the project admin key only from a private environment variable or secure stdin.
- Prefer `--key-stdin` for ALab admin commands; avoid inline key arguments in commands that may be logged.
- Never print, commit, write to prompts, or pass the project admin key to workers.
- When launching a worker, remove admin/root credentials from the worker environment:

```sh
env -u ALAB_PROJECT_KEY -u ALAB_ROOT_KEY \
  codex exec -C "$WORKTREE_PATH" --sandbox workspace-write - < "$WORKER_PROMPT"
```

- If a worker needs ALab CLI state writes, add only the specific ALab home/cache/shared directories required for `alab run` or `submit`; do not add the repository root, the whole `.run` directory, `.run/secrets`, `project.env`, or any directory containing admin/root keys. Preflight the worker path before launch and refuse repo root, `.run`, or secret paths as `codex exec -C`.

## Capabilities

This is a capability guide, not a required sequence. Use the capabilities that fit the project objective:

- Inspect project state with `alab project show`, `alab project config show`, `alab status`, and project-scoped audit or observe commands.
- Create new experiments from the project default source, explicit sources, or visible predecessor experiments when continuation is useful.
- Coordinate experiment lineage by recording experiment ids, worktree paths, source refs, tags, from-experiment choices, and selected commits such as `best`, `final`, or `latest`.
- Launch worker agents in experiment worktrees without project admin or root credentials. Provide task instructions and non-secret helper variables only; let workers use their worktree tokens for `alab run` and `alab submit`, keep writable side directories as narrow as possible, and describe added directories as CLI state rather than editable source.
- Observe project-visible evidence across experiments, runs, artifacts, logs, and annotations. Prefer reward, parse status, warning codes, metrics, best/final commits, and submitted refs over free-form worker claims.
- Treat reward parse failures as contract failures first. For file or Harbor rewards, check that reward JSON contains only finite numeric metrics and move detailed diagnostics to artifacts or hidden/visible logs as appropriate.
- Manage project-scoped configuration, environment variables, secrets, validation, sources, tags, and lifecycle state only when they are part of the requested project objective.
- Use dry-run remove commands before destructive lifecycle actions, and record blockers or cleanup consequences before using force/confirm.
- Produce controller summaries that state what was created or changed, which experiments and runs matter, what credentials were deliberately withheld from workers, and what follow-up remains.

## Command Reference

Read [references/commands.md](./references/commands.md) before using project-scoped admin commands, launching workers, or performing lifecycle cleanup.
