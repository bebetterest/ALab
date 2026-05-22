# ALab Global Admin Commands

## Recommended Root Invocation

Use stdin for root key commands:

```sh
printf '%s\n' "$ALAB_ROOT_KEY" | alab --key-stdin key list --root
```

Disable shell tracing and redact command transcripts before sharing. Use ignored local files for generated keys.

## Root Surface

Global admins may use:

```text
alab auth init
alab auth root regenerate
alab config show|set|reset|validate
alab key create --project <project_id> --role admin
alab key list --root
alab key list --project <project_id>
alab key revoke <key_id>
alab context show|repair
alab project init local|git|empty|harbor|skydiscover ...
alab project list|show|archive|unarchive|remove ...
alab catalog skydiscover add|update|show|remove ...
alab cache prune ...
alab backup prune ...
alab audit list|show ...
```

## Function Details

Each entry lists the function, purpose, important parameters, and how to use the result.

- **`auth init`**: Create a new ALab home and root key.
  Parameters: Optional `--home <path>`; no credential required.
  Notes: Prints the raw root key exactly once; store it only in an ignored or secure location.
- **`auth root regenerate`**: Replace the active root key.
  Parameters: Use root credential through global `--key-stdin` or equivalent secure input.
  Notes: Revokes the previous root verifier and prints the replacement root key exactly once.
- **`config show`**: Inspect ALab home-level config and validity.
  Parameters: No required args.
  Notes: Shows schema version, output format, preview bytes, lock timing, busy timeout, and config validity.
- **`config set`**: Change one ALab home-level setting.
  Parameters: Required `<field> <toml-literal>`; allowed fields include output, storage timeout, and lock timing fields.
  Notes: `output.format` only accepts TOML string `"text"`.
- **`config reset`**: Reset one home-level setting or all config.
  Parameters: Required `<field>` or `--all`.
  Notes: Use to recover from bad local config values; no root key required.
- **`config validate`**: Validate home config and optionally refresh runtime capability checks.
  Parameters: Optional `--refresh-capabilities`.
  Notes: Use before Docker/runner-sensitive work or after environment changes.
- **`key create`**: Create a project admin key for a controller.
  Parameters: Required `--project <project_id>`; optional `--role admin`.
  Notes: Root-only; prints raw admin key exactly once.
- **`key list --root`**: Inspect root credential rows.
  Parameters: Required `--root`; conflicts with `--project`.
  Notes: Use to confirm active/revoked root credential ids without exposing raw keys.
- **`key list --project`**: Inspect project admin credential rows.
  Parameters: Required `--project <project_id>` unless project context supplies it.
  Notes: Root/admin may inspect project credentials; does not render raw admin keys.
- **`key revoke`**: Revoke a credential by id.
  Parameters: Required `<key_id>`; optional `--project <project_id>`.
  Notes: Root-only for revocation; do not revoke the wrong active key without checking audit and scope.
- **`context show`**: Inspect path context markers and registered ALab path records.
  Parameters: Optional `--path <dir>`; default `.`.
  Notes: Use before repair or when a command is running in an unexpected project/experiment/inspection context.
- **`context repair`**: Repair a path context marker when authorized.
  Parameters: Required `--path <dir>`.
  Notes: Root/admin can repair in scope; token self-repair has strict Git branch or pinned-commit checks.
- **`project init`**: Create a project, source, config version, baseline validation, and project admin key.
  Parameters: Mode `local|git|empty|harbor|skydiscover`; required `--config`; common `--name`, `--task`, `--goal`, `--skip-baseline-test`; mode-specific source/task fields; source size limits.
  Notes: Runtime behavior comes from config only. Generated project admin key is printed once after project row creation.
- **`project list|show`**: Inspect retained projects.
  Parameters: `list` accepts `--include-archived`; `show` accepts optional `--project <project_id>`.
  Notes: Use to find project ids, statuses, active config version, default source, runner, reward, and visibility.
- **`project archive|unarchive`**: Toggle project lifecycle status.
  Parameters: Optional `--project <project_id>`.
  Notes: Archive can be blocked by active locks or maintenance.
- **`project remove`**: Remove an archived project and its retained tree by audited cascade.
  Parameters: Required `--cascade`; plus `--dry-run` or `--force --confirm <project_id>`; optional `--project`, `--reason`.
  Notes: Root-only and destructive. Always dry-run first; actual remove stages filesystem paths through ALab trash.
- **`catalog skydiscover add|update`**: Install or change the pinned SkyDiscover catalog.
  Parameters: Optional `--origin-url <url>`; exactly zero or one of `--ref <ref>` or `--commit <full_sha>`.
  Notes: Prefer `--commit` for reproducible examples and releases. `update` requires a clean ALab-managed catalog.
- **`catalog skydiscover show`**: Inspect active SkyDiscover catalog metadata.
  Parameters: No catalog selector needed.
  Notes: Must not fetch from the network; use to confirm pinned commit and local path.
- **`catalog skydiscover remove`**: Remove active SkyDiscover catalog metadata and local checkout.
  Parameters: Required `--force --confirm skydiscover`; optional `--reason`.
  Notes: Blocked while active configs or open experiments reference the catalog.
- **`cache prune`**: Remove ALab-owned non-authoritative caches.
  Parameters: Selectors: `--docker-images`, `--skydiscover-envs`, `--trash --older-than <days>`, `--trash-all`, or `--all`.
  Notes: `--all` conflicts with individual selectors; trash retention days must be non-negative.
- **`backup prune`**: Remove old pre-upgrade backups.
  Parameters: Exactly one of `--keep <n>` or `--older-than <days>`.
  Notes: Retention values must be zero or greater; output includes pruned paths and audit id.
- **`audit list`**: Search global or project-scoped audit events.
  Parameters: Optional `--project`, `--object-type`, `--object-id`, `--action`, `--actor`, time bounds, `--limit`, `--offset`.
  Notes: Root can query globally; project admin is scoped to the project.
- **`audit show`**: Inspect one audit event and sanitized metadata.
  Parameters: Required `<audit_id>`; optional `--project <project_id>`.
  Notes: Use to verify credential, project, catalog, cleanup, repair, and remove actions without raw secrets.

Root can also inspect or maintain project-scoped resources when needed, but should delegate normal experiment coordination to the project controller role.

## Project Initialization

Local project:

```sh
printf '%s\n' "$ALAB_ROOT_KEY" | alab --key-stdin project init local \
  --config alab.project.toml \
  --source-path . \
  --name "$PROJECT_NAME" \
  --task "$TASK"
```

SkyDiscover project:

```sh
printf '%s\n' "$ALAB_ROOT_KEY" | alab --key-stdin catalog skydiscover add --commit "$SKYDISCOVER_COMMIT"

printf '%s\n' "$ALAB_ROOT_KEY" | alab --key-stdin project init skydiscover \
  --config alab.project.toml \
  --name "$PROJECT_NAME" \
  --task "$TASK"
```

`project init` prints the generated project admin key exactly once after the project record is written. Capture it into an ignored local file or approved secret store, then pass only the project admin key to project controllers.

## Catalog Rules

- Pin SkyDiscover with `--commit` when reproducibility matters.
- `catalog skydiscover show` must not fetch from the network.
- Missing catalog paths do not auto-update.
- `catalog skydiscover remove` is blocked while active configs or open experiments reference the catalog.

## Cleanup Rules

Use cleanup only for non-authoritative data:

```text
alab cache prune --docker-images
alab cache prune --skydiscover-envs
alab cache prune --trash --older-than <days>
alab cache prune --trash-all
alab cache prune --all
alab backup prune --keep <n>
alab backup prune --older-than <days>
```

For destructive project or lifecycle removal, run dry-run first, review blockers, then require exact confirmation.

## Handoff

A global admin handoff should include:

- ALab home path and home id when safe,
- project id, project name, and active config version,
- generated project admin key delivery path or confirmation that it was handed off,
- catalog pinned commit when applicable,
- validation id and validation status,
- cleanup or audit actions performed.
