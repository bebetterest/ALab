---
name: alab-global-admin
description: Use when administering an ALab home with a root key, including home bootstrap, root and admin credential management, project initialization, SkyDiscover catalog management, global cache or backup pruning, and audit inspection without doing experiment work.
---

# ALab Global Admin

## Overview

Use this skill for root-level ALab administration. The global admin owns ALab home setup, root credential rotation, project admin key creation or revocation, project initialization, SkyDiscover catalog lifecycle, cache and backup pruning, global audit inspection, and the root-only local read-only dashboard.

This skill does not do experiment implementation. After creating a project, creating an experiment as part of setup, or issuing a project admin key, delegate follow-up project-level operations to a separate session/thread with the project admin key and the `alab-project-controller` skill/instructions, and experiment implementation to a separate session/thread in the experiment worktree with the `alab-experiment-worker` skill/instructions and only that experiment's token context. If a separate session is not available, use a subagent or worker process with equivalent project/worktree/token isolation. User instructions override this preference; otherwise, keep the root-admin session focused on root-scoped administration.

## Credential Rules

- Treat the root key as a one-time-rendered local secret.
- Prefer `--key-stdin` for root commands; avoid inline key arguments in logs.
- Do not store raw root/admin keys in tracked files, prompts, commits, screenshots, reports, or command transcripts.
- Store generated project admin keys only in ignored local secret files, such as an example-local `.run/secrets/` directory, or a user-approved secure location.
- When delegating to a separate session/thread or subagent, pass only the credential needed for that task and scope. Root keys stay only with root-admin sessions. Project admin keys go only to sessions doing project-level work for that project. Experiment worktree or inspection tokens go only to sessions working in that experiment worktree or inspection checkout. Use ignored secret files, private environment variables, or secure stdin rather than prompts.
- Provide the matching ALab skill/instructions to delegated sessions or subagents: `alab-project-controller` for project-level work and `alab-experiment-worker` for experiment worktree work.
- After handoff, keep root/admin keys out of worker prompts, worker sandboxes, shared run directories, and non-secret reports.
- If a root key is lost, ALab V1 cannot recover it; do not attempt ad hoc DB edits.

## Capabilities

This is a capability guide, not a required sequence. Use the capabilities that fit the administrative objective:

- Bootstrap an ALab home with `alab auth init` only when no home exists, and inspect home health with `alab config show` or `alab config validate`.
- Use `alab feedback` for local ALab/tooling suggestions, questions, or bug reports that should be retained under the home without adding database rows; use root-only `alab feedback list|show|archive` to triage those file-backed records.
- Use `alab dashboard` when a root user needs browser-based read-only inspection of the local home. Treat the dashboard as local-only; do not share the token URL or use it for mutation workflows.
- Manage root credentials deliberately. Rotate root only with explicit intent, and treat replacement keys as one-time-rendered secrets.
- Create, list, and revoke project admin keys for delegated project-level sessions. Revoke only after identifying the key id, project scope, and expected impact.
- Initialize projects from local, Git, empty, Harbor, or SkyDiscover sources using config files. Capture the generated project admin key exactly once, store it only in an ignored secret location, and hand it off securely to a project-level session with `alab-project-controller` skill/instructions, never to an experiment worker.
- When further project setup, experiment creation, or experiment coordination is needed after root-level setup, start a separate project-level session with the project admin key and `alab-project-controller` skill/instructions. When worktree changes are needed, start a separate session in the experiment worktree with `alab-experiment-worker` skill/instructions and only that experiment's token context. If unavailable, use a subagent or worker process with equivalent isolation instead of doing that work directly in the global-admin session.
- When project initialization fails during baseline validation, preserve the redacted logs and distinguish environment/capability failures from reward-contract failures such as non-numeric reward metrics.
- Manage SkyDiscover catalog lifecycle with exact commit pinning, no-network `show`, active-reference blockers, and explicit remove confirmation.
- Maintain global non-authoritative state with cache, trash, and backup prune commands.
- Inspect global or project audit records to verify sensitive lifecycle events, credential changes, catalog changes, cleanup, and project initialization.
- Use dry-run where available before destructive removal, and delegate routine experiment coordination to a project-level session with the project admin key and worktree editing to an experiment worktree session with token context.

## Command Reference

Read [references/commands.md](./references/commands.md) before root-only actions, project initialization, catalog changes, or cleanup.
