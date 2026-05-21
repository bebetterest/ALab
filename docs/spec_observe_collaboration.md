# ALab V1 Observe And Collaboration Spec

This spec defines visibility, observe commands, log access, tags, artifact export, and annotations.

## 1. Visibility Model

Project visibility config:

```toml
[visibility]
scope = "same_project" # none|same_project|explicit
experiment_ids = []
```

Effective visibility:

- Current project policy is evaluated at authorization time.
- Experiment policy is stored at experiment creation time and acts as a per-experiment upper bound.
- Effective token visibility is the intersection of the current project policy and the source experiment's stored experiment policy.
- Later project policy changes can narrow or broaden existing token authorization within the experiment policy bound.
- Later project policy changes cannot grant access outside the source experiment's stored experiment policy.
- Regenerated tokens use the same visibility formula and do not rewrite experiment policy.
- Tags do not affect authorization.
- An experiment or inspection token can always inspect its own experiment records. Visibility scope controls access to other experiments.
- Root/admin in project context can inspect and maintain all project records.
- Experiment token in experiment context can inspect only effective visible records.
- Inspection token in inspection context uses the same effective visibility formula and cannot mutate.
- Archived experiments are hidden from list/search/best by default, but archive state is not an authorization policy field.

Visibility selector meanings:

- `none`: no other experiment records visible.
- `same_project`: records from experiments in same project.
- `explicit`: only listed experiment ids.

Public access:

- Public no-key experiment creation is enabled by default.
- Public no-key checkout is not allowed.
- Public no-key observe history is not allowed.
- Public no-key `exp create --from-exp` uses public inheritance visibility, not token visibility. Public inheritance visibility is the intersection of the current project visibility policy evaluated from the public project context and the source experiment's stored visibility upper bound. After intersection, `none` allows no experiment source, `same_project` allows open or closed experiments in the project, and `explicit` allows only listed open or closed experiment ids. No raw experiment token is involved, but the source experiment's stored upper bound still caps public inheritance. This is a source-inheritance operation, not an observe command.
- No-key project status may render only a safe project summary.
- Historical observation for public projects must happen from an experiment worktree or inspection checkout through a valid token.

## 2. Observe Commands

Primary observe commands:

```text
alab observe experiments list [filters]
alab observe experiments search --query <text> [filters]
alab observe experiments show <exp_id>
alab observe experiments best [filters]
alab observe runs list [filters]
alab observe runs show <run_id>
alab observe runs archive <run_id>
alab observe runs unarchive <run_id>
alab observe runs remove <run_id> (--dry-run|--force --confirm <run_id>) [--cascade] [--reason <text>]
alab observe artifacts list [filters]
alab observe artifacts show <artifact_id>
alab observe artifacts export <artifact_id> --out <path> [--overwrite] [--include-archived]
alab observe artifacts archive <artifact_id>
alab observe artifacts unarchive <artifact_id>
alab observe artifacts remove <artifact_id> (--dry-run|--force --confirm <artifact_id>) [--cascade] [--reason <text>]
alab observe logs list [filters]
alab observe logs show <log_id> [--include-hidden]
alab observe logs export <log_id> --out <path> [--overwrite] [--include-hidden] [--include-archived]
alab observe logs archive <log_id>
alab observe logs unarchive <log_id>
alab observe logs remove <log_id> (--dry-run|--force --confirm <log_id>) [--cascade] [--reason <text>]
alab observe annotations list [filters]
alab observe annotations show <annotation_id> [--history]
```

Aliases:

```text
alab exp list|search|show|best
alab runs list|show|archive|unarchive|remove
alab artifacts list|show|export|archive|unarchive|remove
alab logs list|show|export|archive|unarchive|remove
alab annotations list|show
```

Context behavior:

- Project context requires root/admin key and can inspect all project records.
- Experiment context uses token visibility.
- Inspection context uses inspection token visibility.
- Archived records are hidden by default from list/search/best but can be shown by id when authorized.
- Artifact and log export of archived records still requires explicit `--include-archived`.

## 3. Search, Pagination, And Sorting

Search:

- V1 uses plaintext local records and scans SQLite/file-backed records in process.
- `--query` is case-insensitive substring matching.
- Search corpus includes project/experiment names and goals, task text visible to the caller, tags, final summaries, feedback, and latest annotation bodies.
- Search does not scan run stdout/stderr logs, hidden logs, artifact bytes, or historical annotation revisions in V1.

Pagination:

- `list`, `search`, and `best` commands support `--limit <n>` and `--offset <n>`.
- Default `--limit` is `50`.
- `--limit` must be between `1` and `500`.
- `--offset` must be zero or greater.

Sorting:

- Commands support `--sort <field>:<asc|desc>` unless a command explicitly documents a smaller surface.
- Sort fields are command-specific whitelists.
- Unknown sort fields fail with `CONFIG_INVALID`.
- Default sorting is by most relevant timestamp descending for list/search and by reward ranking for best.
- Experiment list/search sort fields: `created`, `updated`, `name`, `status`, `reward`.
- Experiment best does not accept `--sort`; it always uses reward-policy ranking.
- Run list sort fields: `started`, `ended`, `reward`, `status`, `config-version`, `exit-code`.
- Artifact list sort fields: `created`, `path`, `size`, `status`, `content-hash`.
- Log list sort fields: `created`, `stream`, `size`, `stored-bytes`, `hidden`, `truncated`.
- Annotation list sort fields: `created`, `updated`, `target-type`, `target-id`, `status`, `created-by`.
- Rows with nullable sort values are always placed after rows with concrete values.

## 4. Filters

Experiment list/search/best filters:

- `--status` accepts `open`, `closed`, or `archived`
- repeated `--tag`
- `--source-id`
- `--name-query`
- `--reward-min`
- `--reward-max`
- When both reward bounds are supplied, `--reward-min` must be less than or equal to `--reward-max`.
- `--config-version` accepts a positive config version number
- `--created-after`
- `--created-before`
- `--updated-after`
- `--updated-before`
- `--include-archived`

Matching `after` and `before` time bounds in the same field family must be ordered.
Repeated `--tag` filters use AND semantics.

Run list filters:

- `--exp`
- `--status`
- `--config-version` accepts a positive config version number
- `--commit` accepts a full or abbreviated hexadecimal commit SHA prefix
- `--reward-min`
- `--reward-max`
- When both reward bounds are supplied, `--reward-min` must be less than or equal to `--reward-max`.
- `--runner-type` accepts `local`, `docker`, `harbor`, `skydiscover_docker`, or `skydiscover_python`
- `--exit-code`
- `--failure-reason-query`
- `--started-after`
- `--started-before`
- `--ended-after`
- `--ended-before`
- `--include-archived`

Matching `after` and `before` time bounds in the same field family must be ordered.

Artifact list filters:

- `--exp`
- `--run`
- `--validation`
- `--root` accepts `workspace` or `run`
- `--status`
- `--path-query`
- `--content-hash` accepts `sha256:<64-hex>`
- `--created-after`
- `--created-before`
- `--size-min` accepts a non-negative integer byte count
- `--size-max` accepts a non-negative integer byte count
- When both size bounds are supplied, `--size-min` must be less than or equal to `--size-max`.
- `--include-archived`

Matching `after` and `before` time bounds in the same field family must be ordered.

Log list filters:

- `--exp`
- `--run`
- `--validation`
- `--stream` accepts `stdout`, `stderr`, `hidden_stdout`, or `hidden_stderr`
- `--truncated`
- `--created-after`
- `--created-before`
- `--include-hidden`
- `--include-archived`

Matching `after` and `before` time bounds in the same field family must be ordered.

Annotation list filters:

- `--target-type`
- `--target-id`
- `--author`
- `--created-by`
- `--private`
- `--query`
- `--created-after`
- `--created-before`
- `--updated-after`
- `--updated-before`
- `--include-archived`
- Object-backed `--target-id`/`--target` values must be complete experiment, run, or artifact ids when their target type is selected or inferable. `--created-by` must be a complete experiment or credential id.

Matching `after` and `before` time bounds in the same field family must be ordered.

## 5. Best Ranking

Rules:

- Each visible experiment contributes at most one qualifying run.
- Qualifying run must have parsed numeric reward.
- Default excludes failed, error, timeout, running, and interrupted runs.
- Default excludes archived runs.
- Ranking uses the reward direction of the comparable reward policy set.
- By default, `best` compares runs whose bound reward policy identity matches the current active project reward policy. Reward policy identity includes reward type, direction, primary metric, and reward extractor fields that affect the numeric value.
- Reward policy identity comparison is independent of config version. Runs from different config versions may be ranked together only when their reward policy identity matches.
- If the project is currently invalid, default `best` still uses the active valid config's reward policy identity. If the project has no active valid config, `best` fails with `PROJECT_INVALID` and asks for an explicit `--config-version`.
- When `--config-version <n>` is supplied, `<n>` must be positive and `best` compares only visible runs bound to that config version.
- Runs with incompatible reward policy identity are excluded. `best` renders `BEST_INCOMPARABLE_RUNS_EXCLUDED` as a warning block with an excluded count.
- Ties sort by run ended time descending, then experiment id.

## 6. Runs Show And Logs

`observe runs show`:

- Shows fixed-size stdout and stderr previews.
- Shows log ids for full log access.
- Shows log sizes, stored byte counts, truncation flags, and hidden log availability as a boolean for admin/root.
- Does not show full logs.
- Does not show hidden log contents.

`observe logs list|show|export`:

- Visible logs are available to authorized tokens according to visibility.
- Hidden logs require root/admin and explicit `--include-hidden`.
- `--include-hidden` is rejected for token-only contexts.
- Archived logs are hidden from list by default.
- Showing an archived log by id, including log text, requires authorization but not `--include-archived`.
- Exporting an archived log requires `--include-archived`.
- `logs show` renders safe decoded text from stored bytes, respecting output size limits.
- `logs export` writes exact stored bytes.
- Export fails with `OUTPUT_EXISTS` if output exists unless `--overwrite` is supplied.
- Export parent directory must exist; ALab does not create missing parent directories for log exports.

Hidden logs:

- Hidden logs include Harbor verifier raw stdout/stderr and SkyDiscover evaluator raw stdout/stderr.
- Hidden logs are file-backed and indexed in SQLite.
- Hidden logs are not artifacts.
- Token-visible commands may show safe hidden-log summaries only when those summaries do not reveal hidden asset contents.

## 7. Artifact Export

Commands:

```text
alab observe artifacts show <artifact_id>
alab observe artifacts export <artifact_id> --out <path> [--overwrite] [--include-archived]
```

Rules:

- Default fails if output path exists.
- `--overwrite` replaces existing files.
- Existing output path without `--overwrite` fails with `OUTPUT_EXISTS`.
- Archived artifacts can be shown by id when authorized. Exporting an archived artifact requires `--include-archived`.
- Parent directory must exist.
- Export writes exact captured bytes.
- Artifact export does not redact `secret_env` values from artifact bytes.
- Hidden assets are never valid artifacts and cannot be exported through this command.

## 8. Tags

Commands:

```text
alab exp tag add <exp_id> <tag> [--project <project_id>]
alab exp tag remove <exp_id> <tag> [--project <project_id>]
alab exp tag list <exp_id> [--project <project_id>]
```

Permissions:

- Experiment token can manage tags on its own experiment.
- Root/admin can manage tags on any experiment in the project.
- Inspection tokens cannot manage tags.

Rules:

- Tags are metadata and never grant visibility.
- Tags normalize to lowercase slug form.
- Tags are limited to 64 bytes after lowercase ASCII slug normalization.
- Duplicate normalized tags are ignored with stable output rather than creating duplicates.

## 9. Annotation Commands

Commands:

```text
alab annotate add --target <target> --body <text>|--body-file <path> [--author <label>] [--private] [--private-to-exp <exp_id>]
alab annotate edit <annotation_id> --body <text>|--body-file <path> [--author <label>]
alab annotate archive <annotation_id>
alab annotate unarchive <annotation_id>
alab annotate remove <annotation_id> (--dry-run|--force --confirm <annotation_id>) [--reason <text>]
alab observe annotations list [filters]
alab observe annotations show <annotation_id> [--history]
```

Targets:

```text
exp:<exp_id>
run:<run_id>
artifact:<artifact_id>
path:<exp_id>@<commitish>:<repo_path>
lines:<exp_id>@<commitish>:<repo_path>:<start>-<end>
path:<repo_path>
lines:<repo_path>:<start>-<end>
```

Commitish:

- Supports common aliases `HEAD`, `head`, `latest`, `final`, and `best`.
- Supports full or unambiguous commit SHA.
- May support registered ALab branch names when root/admin invokes from project context.
- Resolves to one concrete commit SHA at annotation creation time.
- Stored annotations never retain a moving alias as the authoritative target.
- Stored annotations keep normalized target details in `annotations.target_json` so line ranges, repo paths, resolved experiment ids, and resolved commits do not depend on reparsing display strings.

Path and line rules:

- Path and line targets must use normalized forward-slash repo-relative paths with no absolute, Windows-absolute, empty, `.`, `..`, backslash, NUL, or newline components.
- Line ranges are positive integer 1-based inclusive ranges with `end >= start`.
- File/line targets are anchored to an experiment and resolved commit.
- `path:` targets require that the target path exists at the resolved commit as a Git blob or tree.
- `lines:` targets require that the target path exists at the resolved commit as a Git blob and that the inclusive line range is valid for the captured file contents.
- Current experiment shorthand is allowed only in experiment context and resolves to the current experiment's current HEAD commit at annotation creation time.
- Current experiment shorthand requires a clean worktree. If staged, unstaged, deleted, renamed, copied, or untracked non-ignored changes exist, annotation creation fails rather than anchoring to uncommitted content.

Visibility:

- Annotation can target visible records.
- Annotation defaults to project visibility.
- Annotation visibility never expands target visibility. A caller can see a project-visible annotation only when the caller can also see the target record under the normal visibility rules.
- `--private` restricts visibility to the creating experiment and root/admin, even when the target belongs to another visible experiment.
- Experiment-private annotations are bound to the creating experiment identity, not to one raw token value. A regenerated worktree token for the same experiment can see and edit that experiment's private annotations under the normal creating-experiment ownership rules.
- In project context, root/admin must use `--private-to-exp <exp_id>` to create an experiment-private annotation.
- Annotation target object ids and `--private-to-exp` experiment ids are validated as complete ALab ids before body-file reads or body storage.
- Private annotations remain private even if project visibility later broadens.
- Inspection tokens cannot add or edit annotations.
- Validation-owned artifact rows do not carry an experiment id and are rejected as annotation targets with `CONFIG_INVALID`; use an experiment/path/line target or a run-owned artifact target when the annotation must bind to a concrete experiment.

Body input:

- Annotation bodies are UTF-8 text.
- Body is limited to 65536 bytes after encoding.
- Body input accepts exactly one of direct text or file input.
- V1 does not support `--body-stdin`.
- Annotation bodies must not contain exact active `secret_env` values for the authoring experiment's bound config version. If an exact secret value is found, creation or edit fails without storing a revision.
- When root/admin creates or edits an annotation from project context, the authoring secret check uses the target experiment's bound config version. Targets that do not resolve to exactly one experiment are rejected with `CONFIG_INVALID` before body storage and must be rewritten to a target with a concrete experiment identity; root/admin can then use `--private-to-exp <exp_id>` when experiment-private visibility is needed.

Revision and archive:

- Annotation edits create revisions.
- Creator experiment token can edit annotations it created.
- A regenerated worktree token for the same experiment is treated as the creator experiment token for experiment-private annotation visibility and edits. Revoking an old token does not make that experiment's private annotations root/admin-only when a new active worktree token exists.
- Root/admin can edit any annotation in the project.
- Edits cannot change target.
- `annotate archive` follows the same authorization rules as edit.
- `annotate unarchive` follows the same authorization rules as archive.
- `annotate remove` follows the same authorization rules as archive, requires the annotation to already be archived, deletes all revisions in the same audited transaction, records `deleted_revision_count`, and has no filesystem targets.
- Archive tombstones the annotation without deleting revisions.
- Archived annotations are hidden from list/search by default but can be shown by id when authorized.

## 10. Public Safe Status

Public safe status may include:

- project id
- project name
- task
- goal
- project status
- default source id/name/content hash
- mutable summary
- visibility summary
- runner type
- timeout
- working directory
- reward type
- reward direction
- primary metric
- artifact/log limits
- next action

Public safe status must not include:

- project history
- experiment records
- run records
- artifacts
- annotations
- `env` values
- `secret_env` names or values
- full runner command
- generated verifier/evaluator commands
- hidden assets
- raw hidden logs
- absolute catalog paths
- adapter staging paths
- baseline failure logs

If the project is invalid, no-key public status renders only invalid status and an admin next action.
