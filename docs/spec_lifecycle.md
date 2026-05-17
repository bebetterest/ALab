# ALab V1 Lifecycle Spec

This spec defines archive, unarchive, remove, restore, repair, revoke, regenerate, garbage collection, pruning, and audit behavior for ALab V1. Other subsystem specs reference this document for lifecycle semantics.

## 1. Lifecycle Vocabulary

- `archive`: reversible soft state that hides or blocks normal use while keeping DB rows, Git refs, logs, artifacts, tokens, annotations, and filesystem data unless another cleanup command acts. Archive commands are idempotent.
- `unarchive`: restores an archived object. Project and experiment restore `pre_archive_status`; closed experiments never reopen. Unarchive commands are idempotent.
- `remove`: permanent deletion of a supported authoritative record or object tree. Remove requires the target object to already be archived unless this spec names an exception.
- `restore`: rebuilds a removable filesystem context, mainly submit-capable experiment worktrees.
- `repair`: fixes path registry entries after directory moves. It does not restore deleted paths, regenerate credentials, or change object status.
- `revoke` and `regenerate`: credential lifecycle only. Credentials are never hard-removed in V1.
- `gc` and `prune`: cleanup for non-authoritative or unreferenced data such as secret values, caches, and backups.
- `trash`: temporary ALab-owned holding area under `~/.ALab/tmp/trash/<audit_id>/` used during filesystem hard remove.

## 2. Hard Remove Rules

All authoritative `remove` commands use the same safety contract:

```text
(--dry-run|--force --confirm <object_id>) [--cascade] [--reason <text>]
```

Rules:

- The target authoritative object must already be archived.
- `--dry-run` performs dependency checks and renders blockers plus deletion counts without writing audit rows or deleting data. If the target is not archived, dry-run exits `0` and renders a stable `target_not_archived` blocker.
- Actual deletion requires both `--force` and `--confirm <object_id>`.
- `--confirm` must exactly match the target object id.
- A remove command that provides neither `--dry-run` nor `--force --confirm <object_id>` fails with `CONFIG_INVALID`.
- Actual deletion with missing `--force`, missing `--confirm`, or a wrong confirmation id fails with `CONFIG_INVALID`.
- `--reason` is optional UTF-8 text and is limited to 65536 bytes after encoding.
- `--cascade` is explicit. It may delete dependent authoritative objects only when every dependent authoritative object is already archived.
- If any dependent authoritative object is active, remove fails and renders stable blocker fields.
- Project remove and experiment remove define explicit whole-tree cascade exceptions below. Those exceptions do not apply to source remove, run remove, validation remove, artifact remove, log remove, or annotation remove.
- Actual hard remove still fails with `RESOURCE_BUSY` when the target is not archived.
- Hard remove writes one `audit_events` row before or in the same transaction as deleting DB rows.
- Filesystem hard remove first tries to rename affected ALab-owned files or directories into `~/.ALab/tmp/trash/<audit_id>/`.
- If the target path cannot be moved to home trash because it is on another filesystem, ALab falls back to an atomic rename in the target's parent directory named `.alab-trash-<audit_id>`. Audit metadata records only a sanitized same-parent trash label, not hidden asset contents or raw secret data.
- After the filesystem move succeeds, ALab writes audit/DB changes, then immediately attempts to delete the trash directory.
- If the audit/DB transaction fails after the filesystem move, ALab must best-effort rename the trash path back to the original path. If restore fails, the command returns `STORAGE_ERROR` and renders a repair next action.
- If immediate trash deletion fails after the audit/DB transaction succeeds, the audit event records the relative or sanitized trash path and `alab cache prune --trash --older-than <days>` or `alab cache prune --trash-all` is the cleanup path.
- Audit metadata must be sanitized and must not include raw keys, tokens, secret values, verifier hashes, hidden asset contents, or raw hidden logs.

Archive-first exceptions:

- `exp worktree remove`.
- `exp checkout remove`.
- `cache prune`, including trash cleanup.
- `backup prune`.
- temporary directory cleanup.
- `catalog skydiscover remove`.
- `project secret gc --apply`, which only deletes unreferenced raw secret values.

## 3. Project Lifecycle

Commands:

```text
alab project archive [--project <project_id>]
alab project unarchive [--project <project_id>]
alab project remove [--project <project_id>] (--dry-run|--force --confirm <project_id>) --cascade [--reason <text>]
```

Rules:

- Archive and unarchive require root/admin.
- Archive is a pure state change and stores `pre_archive_status`.
- Archive is idempotent when the project is already archived. It returns success, renders the existing archived state, and does not write a duplicate audit event.
- Archive fails with `RESOURCE_BUSY` when active validation, source import, run, submit, worktree maintenance, or other project maintenance locks exist.
- Unarchive restores `pre_archive_status`.
- Unarchive is idempotent when the project is already unarchived. It returns success, renders the current state, and does not write a duplicate audit event.
- Remove is root-only.
- Project remove requires the project to be archived and requires `--cascade`.
- Project remove is a whole-tree cascade exception. Once the project itself is archived and no active project, validation, source import, run, submit, worktree maintenance, or maintenance locks exist, `project remove --cascade` may delete the project DB tree even when child sources, experiments, runs, validations, artifacts, logs, annotations, and tags are not individually archived.
- Project remove deletes the canonical repo, project artifact/log files, default and custom worktrees registered to the project, project control path, inspection contexts, and dependent records in one audited operation.
- Project admin credentials and experiment tokens are revoked and retained for audit; credential rows are not hard-deleted.

## 4. Source Lifecycle

Commands:

```text
alab source archive <source_id> [--project <project_id>]
alab source unarchive <source_id> [--project <project_id>]
alab source remove <source_id> [--project <project_id>] (--dry-run|--force --confirm <source_id>) [--cascade] [--reason <text>]
```

Rules:

- Source lifecycle commands require root/admin.
- Source archive is blocked only when the source is the active default source.
- Source archive is idempotent when the source is already archived. It returns success and does not write a duplicate audit event.
- Source unarchive restores active status.
- Source unarchive is idempotent when the source is already active. It returns success and does not write a duplicate audit event.
- Source remove requires archived source.
- If a source is referenced by any project config version, remove always fails in V1 because config versions are immutable reproducibility records.
- If a source is referenced by experiments but no project config version references it, remove fails unless `--cascade` is supplied and every dependent experiment is already archived.
- Source remove does not use the project/experiment whole-tree exception. It never deletes active experiments as a side effect.
- Source remove deletes the source row and Git source ref. V1 does not promise immediate Git object garbage collection.

## 5. Experiment Lifecycle

Commands:

```text
alab exp archive <exp_id> [--project <project_id>]
alab exp unarchive <exp_id> [--project <project_id>]
alab exp remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--cascade] [--reason <text>]
```

Rules:

- Archive and unarchive require root/admin.
- Archive is a pure state change and never accepts worktree deletion flags.
- Archive is idempotent when the experiment is already archived. It returns success, renders the existing archived state, and does not write a duplicate audit event.
- Archive fails with `RESOURCE_BUSY` when the experiment has an active run or submit lock.
- Archive stores `pre_archive_status`.
- Unarchive restores `pre_archive_status`; a closed experiment remains closed.
- Unarchive is idempotent when the experiment is already unarchived. It returns success, renders the current state, and does not write a duplicate audit event.
- Remove requires archived experiment.
- Experiment remove is a whole-experiment cascade exception. Once the experiment itself is archived and has no active run or submit lock, `exp remove --cascade` may delete that experiment's runs, logs, artifacts, annotations, tags, inspection contexts, and final submission records even when those child records are not individually archived.
- Experiment remove deletes the experiment branch, worktree and inspection contexts, tags, annotations, runs, logs, artifacts, and final submission records in one audited operation.
- Experiment tokens are revoked and retained for audit.

## 6. Worktree And Inspection Context Lifecycle

Submit-capable worktree commands:

```text
alab exp worktree remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--reason <text>]
alab exp worktree restore <exp_id> [--project <project_id>] --path <dir>
```

Rules:

- Both commands require root/admin.
- Worktree remove may run while the experiment is open, closed, or archived.
- `--dry-run` reports the target path, token revocation target, dirty state when available, and planned trash move without mutating DB rows, writing audit events, or deleting files.
- Worktree remove deletes the submit-capable filesystem worktree, marks its path registry row `removed`, revokes the active worktree token, and sets `experiments.worktree_state = 'removed'`.
- If the registered worktree path is already missing, actual worktree remove reconciles state by marking the path registry row `removed`, revoking the active worktree token, setting `experiments.worktree_state = 'removed'`, and writing an audit event whose metadata records that the filesystem path was already absent.
- Dirty worktree content is discarded only because `--force` is required.
- Actual filesystem deletion uses the same `tmp/trash/<audit_id>/` staging contract as hard remove flows.
- Run and submit require `worktree_state = 'active'`.
- Restore requires a supplied empty or nonexistent path that does not nest inside another registered context.
- Restore checks out the experiment branch HEAD, writes `.alab/context.json`, creates and writes a new worktree token, registers the path, and sets `worktree_state = 'active'`.
- Restore never prints the raw token.

Inspection checkout command:

```text
alab exp checkout remove (--token-id <token_id>|--path <dir>) [--project <project_id>] (--dry-run|--force --confirm <token_id-or-path-hash>) [--reason <text>]
```

Rules:

- Root/admin may remove any inspection checkout in scope.
- An inspection token may remove its own inspection checkout.
- `--dry-run` reports the checkout path, token revocation target, and planned trash move without mutating DB rows, writing audit events, or deleting files.
- Inspection checkout remove deletes the inspection filesystem worktree, revokes the inspection token, and marks the path registry row `removed`.
- If the registered inspection checkout path is already missing, actual checkout remove reconciles state by revoking the inspection token, marking the path registry row `removed`, and writing an audit event whose metadata records that the filesystem path was already absent.
- Actual filesystem deletion uses the same `tmp/trash/<audit_id>/` staging contract as hard remove flows.
- Inspection checkouts have no restore command. Create a new inspection checkout with `alab exp checkout`.

## 7. Run And Validation Lifecycle

Run commands:

```text
alab observe runs archive <run_id>
alab observe runs unarchive <run_id>
alab observe runs remove <run_id> (--dry-run|--force --confirm <run_id>) [--cascade] [--reason <text>]
```

Validation commands:

```text
alab project validation archive <validation_id> [--project <project_id>]
alab project validation unarchive <validation_id> [--project <project_id>]
alab project validation remove <validation_id> [--project <project_id>] (--dry-run|--force --confirm <validation_id>) [--cascade] [--reason <text>]
```

Rules:

- A worktree token may archive and unarchive runs from its own experiment.
- Regenerated worktree tokens inherit this own-experiment run lifecycle capability because the permission is bound to the experiment identity, not to a specific old token value.
- Root/admin may archive and unarchive any run in project scope.
- Run remove is root/admin only and requires archived run.
- Removing the experiment `latest_run_id` recomputes latest from remaining non-removed runs. If no run remains, `latest_run_id` becomes `none` and `latest_commit` remains the experiment branch HEAD.
- Removing the experiment `final_run_id` keeps the experiment closed, preserves final commit, summary, feedback, and refs, and writes `final_run_removed_at`, `final_run_removed_by`, and `final_run_removed_audit_id`.
- Validation lifecycle is root/admin only.
- A validation proving `projects.active_valid_config_version` through `projects.active_validation_id` cannot be archived or removed.

## 8. Artifact And Log Lifecycle

Commands:

```text
alab observe artifacts show <artifact_id>
alab observe artifacts archive <artifact_id>
alab observe artifacts unarchive <artifact_id>
alab observe artifacts remove <artifact_id> (--dry-run|--force --confirm <artifact_id>) [--cascade] [--reason <text>]
alab observe logs archive <log_id>
alab observe logs unarchive <log_id>
alab observe logs remove <log_id> (--dry-run|--force --confirm <log_id>) [--cascade] [--reason <text>]
```

Rules:

- A worktree token may archive and unarchive artifacts and visible logs from its own experiment.
- Regenerated worktree tokens inherit this own-experiment artifact and visible-log lifecycle capability because the permission is bound to the experiment identity, not to a specific old token value.
- Root/admin may archive and unarchive any artifact or log in project scope.
- Artifact and log remove are root/admin only and require archived object.
- Hidden logs may only be archived, unarchived, or removed by root/admin.
- Artifact blobs and log files are deleted only when no remaining row references the same content or file.
- Archived artifact and log rows are hidden from list commands by default.
- Showing archived artifacts or logs by id requires authorization but not `--include-archived`. Exporting archived artifacts or logs requires authorization plus `--include-archived`.

## 9. Annotation And Tag Lifecycle

Annotation commands:

```text
alab annotate archive <annotation_id>
alab annotate unarchive <annotation_id>
alab annotate remove <annotation_id> (--dry-run|--force --confirm <annotation_id>) [--reason <text>]
```

Rules:

- The creating token, project admin, and root may archive, unarchive, and remove annotations within existing visibility and ownership rules.
- Annotation archive tombstones the annotation without deleting revisions.
- Annotation remove deletes all revisions and writes an audit event.
- Tags keep immediate `add`, `remove`, and `list` behavior. Tags do not have archive or unarchive states.

## 10. Credentials, Secrets, Cache, Catalog, And Backup

Audit rules:

- Lifecycle audit events are written for every lifecycle mutation: archive, unarchive, remove, worktree restore/remove, checkout remove, context repair, credential revoke/regenerate, cache prune, backup prune, secret GC, catalog add/update/remove when they mutate local catalog state, project lock stale-clear when it removes locks, and source/catalog/cache cleanup.
- Audit rows use a generic action plus object type model. Valid actions are `add`, `update`, `archive`, `unarchive`, `remove`, `restore`, `repair`, `revoke`, `regenerate`, `prune`, `gc`, and `clear`; object types distinguish project, source, experiment, run, validation, artifact, log, annotation, credential, secret value, cache, backup, catalog, lock, worktree, and inspection checkout events.
- Commands that create an audit event should render `audit id` in success output unless a more specific command contract explicitly forbids rendering it. Rendering an audit id must never reveal raw secrets, verifier hashes, hidden asset contents, or raw hidden logs.
- Ordinary run, submit, tag, annotation edit, and project config/env/secret set/import/unset mutation records remain authoritative in their own tables and do not create lifecycle audit rows unless another lifecycle operation acts on them. `project secret gc --apply` is still audited because it deletes unreferenced raw secret values.

Credential rules:

- Root/admin keys and experiment tokens support revoke and regenerate only.
- No credential hard remove exists in V1.
- Regenerated tokens write to registered or restored paths and never print raw token values.

Secret rules:

- `project secret unset` changes the active project config only.
- `project secret gc --apply` deletes only raw secret values that are not referenced by any project config version.

Cache and backup commands:

```text
alab cache prune [--docker-images] [--skydiscover-envs] [--trash --older-than <days>|--trash-all] [--all]
alab backup prune (--keep <n>|--older-than <days>)
```

Rules:

- Cache and backup prune require root.
- Cache prune deletes only rebuildable cache entries.
- `--trash --older-than <days>` deletes trash entries older than the selected age.
- `--trash-all` deletes all trash entries.
- Top-level `--all` includes Docker image caches, SkyDiscover evaluator environments, and all trash entries.
- Backup prune deletes plaintext migration backups matching the selected retention rule.

Catalog command:

```text
alab catalog skydiscover remove --force --confirm skydiscover [--reason <text>]
```

Rules:

- Catalog remove requires root.
- Catalog remove is blocked when active project configs or any open experiment's bound config reference SkyDiscover catalog tasks or evaluator bundles.
- Catalog remove deletes the local catalog clone and marks catalog metadata removed.
- Closed and archived experiment history must remain observable after catalog removal because safe adapter summaries, metrics, logs, artifacts, and annotations are stored independently of catalog files.

## 11. Audit Visibility

Commands:

```text
alab audit list [--project <project_id>] [filters]
alab audit show <audit_id> [--project <project_id>]
```

Rules:

- Audit commands do not mutate project data.
- Root may list and show audit events globally.
- Project admin may list and show audit events scoped to its project only.
- Audit output renders sanitized metadata and deleted id summaries only.
- Audit output must not include raw keys, tokens, secret values, verifier hashes, hidden asset contents, or raw hidden logs.
