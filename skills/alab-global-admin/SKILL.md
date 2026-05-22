---
name: alab-global-admin
description: Use when administering an ALab home with a root key, including home bootstrap, root and admin credential management, project initialization, SkyDiscover catalog management, global cache or backup pruning, and audit inspection without doing experiment work.
---

# ALab Global Admin

## Overview

Use this skill for root-level ALab administration. The global admin owns ALab home setup, root credential rotation, project admin key creation or revocation, project initialization, SkyDiscover catalog lifecycle, cache and backup pruning, and global audit inspection.

This skill does not do experiment implementation. After creating a project or issuing a project admin key, delegate experiment coordination to `alab-project-controller` and worktree changes to `alab-experiment-worker`.

## Credential Rules

- Treat the root key as a one-time-rendered local secret.
- Prefer `--key-stdin` for root commands; avoid inline key arguments in logs.
- Do not store raw root/admin keys in tracked files, prompts, commits, screenshots, reports, or command transcripts.
- Store generated project admin keys only in ignored local files or a user-approved secure location.
- If a root key is lost, ALab V1 cannot recover it; do not attempt ad hoc DB edits.

## Capabilities

This is a capability guide, not a required sequence. Use the capabilities that fit the administrative objective:

- Bootstrap an ALab home with `alab auth init` only when no home exists, and inspect home health with `alab config show` or `alab config validate`.
- Manage root credentials deliberately. Rotate root only with explicit intent, and treat replacement keys as one-time-rendered secrets.
- Create, list, and revoke project admin keys for project controllers. Revoke only after identifying the key id, project scope, and expected impact.
- Initialize projects from local, Git, empty, Harbor, or SkyDiscover sources using config files. Capture the generated project admin key exactly once and hand it off securely.
- Manage SkyDiscover catalog lifecycle with exact commit pinning, no-network `show`, active-reference blockers, and explicit remove confirmation.
- Maintain global non-authoritative state with cache, trash, and backup prune commands.
- Inspect global or project audit records to verify sensitive lifecycle events, credential changes, catalog changes, cleanup, and project initialization.
- Use dry-run where available before destructive removal, and delegate routine experiment coordination or worktree editing to the project controller and experiment worker roles.

## Command Reference

Read [references/commands.md](./references/commands.md) before root-only actions, project initialization, catalog changes, or cleanup.
