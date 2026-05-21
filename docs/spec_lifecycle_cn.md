# ALab V1 生命周期规范

本文档定义 ALab V1 中 archive、unarchive、remove、restore、repair、revoke、regenerate、garbage collection、prune 和 audit 的行为。其他子系统规范引用本文档作为生命周期语义来源。

## 1. 生命周期术语

- `archive`：可恢复的软状态，用于隐藏或阻止普通使用；除非另一个清理命令执行，否则保留 DB row、Git ref、log、artifact、token、annotation 和文件系统数据。Archive command 是幂等的。
- `unarchive`：恢复 archived 对象。Project 和 experiment 恢复 `pre_archive_status`；closed experiment 永远不会被 reopen。Unarchive command 是幂等的。
- `remove`：永久删除受支持的 authoritative record 或对象树。除本文档明确列出的例外外，remove 要求目标对象已经 archived。
- `restore`：重建可移除的文件系统 context，主要用于 submit-capable experiment worktree。
- `repair`：目录移动后修复 path registry。它不恢复已删除路径，不重新生成 credential，也不改变对象状态。
- `revoke` 和 `regenerate`：只用于 credential 生命周期。V1 永不 hard-remove credential。
- `gc` 和 `prune`：清理非权威或未引用数据，例如 secret value、cache 和 backup。
- `trash`：filesystem hard remove 期间使用的 ALab-owned 临时 holding area，位于 `~/.ALab/tmp/trash/<audit_id>/`。

## 2. Hard Remove 规则

所有 authoritative `remove` 命令使用同一安全契约：

```text
(--dry-run|--force --confirm <object_id>) [--cascade] [--reason <text>]
```

规则：

- 目标 authoritative object 必须已经 archived。
- `--dry-run` 执行 dependency check 并输出 blocker 和 deletion count，但不写 audit row，不删除数据。如果 target 未 archived，dry-run exit `0` 并渲染稳定的 `target_not_archived` blocker。
- 实际删除必须同时提供 `--force` 和 `--confirm <object_id>`。
- `--confirm` 必须与目标 object id 完全一致。
- remove command 如果既未提供 `--dry-run`，也未提供 `--force --confirm <object_id>`，以 `CONFIG_INVALID` 失败。
- `--dry-run` 与 `--force`、`--confirm` 互斥；混合 planning/destructive modes 会在 dry-run rendering、filesystem staging、audit writes 或 DB mutation 之前以 `CONFIG_INVALID` 失败。
- 实际删除缺少 `--force`、缺少 `--confirm` 或确认 id 不匹配，都以 `CONFIG_INVALID` 失败。
- `--reason` 是可选 UTF-8 文本，编码后最多 65536 bytes。
- `--cascade` 必须显式提供。只有当每个依赖 authoritative object 都已 archived 时，它才可以删除依赖对象。
- 如果存在 active 的依赖 authoritative object，remove 失败并输出稳定的 blocker 字段。
- Project remove 和 experiment remove 在下文定义 explicit whole-tree cascade exceptions。这些例外不适用于 source remove、run remove、validation remove、artifact remove、log remove 或 annotation remove。
- Actual hard remove 在 target 未 archived 时仍以 `RESOURCE_BUSY` 失败。
- Hard remove 在删除 DB row 之前或同一事务内写入一条 `audit_events` 记录。
- Filesystem hard remove 首先尝试把受影响的 ALab-owned files/directories rename 到 `~/.ALab/tmp/trash/<audit_id>/`。
- 如果 target path 因为位于另一个 filesystem 而无法移动到 home trash，ALab fallback 到 target parent directory 下名为 `.alab-trash-<audit_id>` 的 atomic rename。Audit metadata 只记录 sanitized same-parent trash label，不记录 hidden asset contents 或 raw secret data。
- Filesystem move 成功后，ALab 写 audit/DB changes，然后立即尝试删除 trash directory。
- 如果 filesystem move 成功后 audit/DB transaction 失败，ALab 必须 best-effort 将 trash path rename 回 original path。如果 restore 失败，command 返回 `STORAGE_ERROR` 并渲染 repair next action。
- 如果 audit/DB transaction 成功后 immediate trash deletion 失败，audit event 记录 relative 或 sanitized trash path，后续通过 `alab cache prune --trash --older-than <days>` 或 `alab cache prune --trash-all` 清理。
- Audit metadata 必须脱敏，不得包含 raw key、token、secret value、verifier hash、hidden asset content 或 raw hidden log。

Archive-first 例外：

- `exp worktree remove`。
- `exp checkout remove`。
- `cache prune`，包括 trash cleanup。
- `backup prune`。
- 临时目录清理。
- `catalog skydiscover remove`。
- `project secret gc --apply`，它只删除未引用的 raw secret value。

## 3. Project 生命周期

命令：

```text
alab project archive [--project <project_id>]
alab project unarchive [--project <project_id>]
alab project remove [--project <project_id>] (--dry-run|--force --confirm <project_id>) --cascade [--reason <text>]
```

规则：

- Archive 和 unarchive 需要 root/admin。
- Archive 是纯状态变更，并存储 `pre_archive_status`。
- Project 已经 archived 时，archive 幂等成功，渲染现有 archived state，不写重复 audit event。
- Active validation、source import、run、submit、worktree maintenance 或其他 project maintenance lock 存在时，archive 以 `RESOURCE_BUSY` 失败。
- Unarchive 恢复 `pre_archive_status`。
- Project 已经 unarchived 时，unarchive 幂等成功，渲染当前 state，不写重复 audit event。
- Project archive/unarchive audit metadata 会记录 previous status、resulting project status 和 archive/unarchive timestamp。
- Remove 仅 root 可执行。
- Project remove 要求 project 已 archived，并要求 `--cascade`。
- Project remove 是 whole-tree cascade exception。只要 project 本身已 archived，且不存在 active project、validation、source import、run、submit、worktree maintenance 或 maintenance locks，`project remove --cascade` 可以删除 project DB tree，即使 child sources、experiments、runs、validations、artifacts、logs、annotations 和 tags 未逐个 archived。
- Project remove 在一次 audited operation 中删除 canonical repo、project artifact/log 文件、注册到该 project 的默认和自定义 worktree、project control path、inspection contexts 和 dependent records。
- Project remove 会先通过 hard-remove trash flow stage project root、control path，以及 active registered worktree/inspection path，再删除 dependent records。已被 project root 覆盖的嵌套路径会在 staging 前去重。
- Project remove audit metadata 存储 sanitized filesystem target count、absent count、trash mode/label、target kind/object id 和 original path hash。
- Project admin credential 和 experiment token 会被 revoke 并保留用于 audit；credential row 不会 hard-delete。
- Project path registry row 会标记为 `removed` 并保留，用于 audit 和 removed-path reuse；不会 hard-delete。

## 4. Source 生命周期

命令：

```text
alab source archive <source_id> [--project <project_id>]
alab source unarchive <source_id> [--project <project_id>]
alab source remove <source_id> [--project <project_id>] (--dry-run|--force --confirm <source_id>) [--cascade] [--reason <text>]
```

规则：

- Source 生命周期命令需要 root/admin。
- Source archive 只在 source 是 active default source 时被阻止。
- Source 已经 archived 时，source archive 幂等成功，不写重复 audit event。
- Source unarchive 恢复 active 状态。
- Source 已经 active 时，source unarchive 幂等成功，不写重复 audit event。
- Source archive/unarchive audit metadata 会记录 previous status、resulting source status 和 archive/unarchive timestamp。
- Source remove 要求 source 已 archived。
- 如果 source 被任何 project config version 引用，V1 中 remove 永远失败，因为 config version 是 immutable reproducibility record。
- 如果 source 被 experiment 引用但未被 project config version 引用，remove 默认失败；只有提供 `--cascade` 且所有依赖 experiment 都已 archived 时才可删除。
- Source remove 不使用 project/experiment whole-tree exception。它绝不作为副作用删除 active experiments。
- Source remove 删除 source row 和 Git source ref。V1 不承诺立即执行 Git object garbage collection。

## 5. Experiment 生命周期

命令：

```text
alab exp archive <exp_id> [--project <project_id>]
alab exp unarchive <exp_id> [--project <project_id>]
alab exp remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--cascade] [--reason <text>]
```

规则：

- Archive 和 unarchive 需要 root/admin。
- Archive 是纯状态变更，绝不接受 worktree 删除参数。
- Experiment 已经 archived 时，archive 幂等成功，渲染现有 archived state，不写重复 audit event。
- 当 experiment 有 active run 或 submit lock 时，archive 以 `RESOURCE_BUSY` 失败。
- Archive 存储 `pre_archive_status`。
- Unarchive 恢复 `pre_archive_status`；closed experiment 保持 closed。
- Experiment 已经 unarchived 时，unarchive 幂等成功，渲染当前 state，不写重复 audit event。
- Experiment archive/unarchive audit metadata 会记录 previous status、resulting experiment status 和 archive/unarchive timestamp。
- Remove 要求 experiment 已 archived。
- Experiment remove 是 whole-experiment cascade exception。只要 experiment 本身已 archived，且不存在 active run 或 submit lock，`exp remove --cascade` 可以删除该 experiment 的 runs、logs、artifacts、annotations、tags、inspection contexts 和 final submission records，即使这些 child records 未逐个 archived。
- Experiment remove 在一次 audited operation 中删除 experiment branch、worktree 和 inspection context、tag、annotation、run、log、artifact 和 final submission record。
- Experiment remove 会在 filesystem staging 后、DB/audit mutation 前删除 experiment branch ref。如果后续 DB/audit mutation 失败，ALab 会 best-effort 把 branch ref 恢复到原 commit，并恢复 staged filesystem paths。
- Experiment remove audit metadata 会记录 branch ref、previous branch commit、该 ref 是否已删除，以及该 ref 是否已提前缺失。
- Experiment token 会被 revoke 并保留用于 audit。

## 6. Worktree 和 Inspection Context 生命周期

Submit-capable worktree 命令：

```text
alab exp worktree remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--reason <text>]
alab exp worktree restore <exp_id> [--project <project_id>] --path <dir>
```

规则：

- 两个命令都需要 root/admin。
- Worktree remove 可在 experiment 为 open、closed 或 archived 时执行。
- `--dry-run` 报告 target path、token revocation target、可获取时的 dirty state 和 planned trash move，不修改 DB row、不写 audit event、不删除文件。
- Worktree remove 删除 submit-capable filesystem worktree，将 path registry row 标记为 `removed`，revoke active worktree token，并设置 `experiments.worktree_state = 'removed'`。
- 如果 registered worktree path 已经缺失，actual worktree remove 会调和状态：将 path registry row 标记为 `removed`，revoke active worktree token，设置 `experiments.worktree_state = 'removed'`，并写 audit event；audit metadata 记录 filesystem path 已经不存在。
- 因为 `--force` 是必需参数，dirty worktree content 会被丢弃。
- 实际 filesystem deletion 使用与 hard remove flow 相同的 `tmp/trash/<audit_id>/` staging contract。
- Run 和 submit 要求 `worktree_state = 'active'`。
- Restore 要求提供空目录或不存在的路径，且该路径不能嵌套在另一个 registered context 内。
- Restore checkout experiment branch HEAD，写入 `.alab/context.json`，创建并写入新的 worktree token，注册路径，并设置 `worktree_state = 'active'`。
- Restore 永不打印 raw token。
- Worktree restore audit metadata 会记录 branch、restored path hash、path registry id、created token id、任何 revoked token id、token mode，以及 resulting worktree state。它绝不存储 raw path 或 raw token。

Inspection checkout 命令：

```text
alab exp checkout remove (--token-id <token_id>|--path <dir>) [--project <project_id>] (--dry-run|--force --confirm <token_id-or-path-hash>) [--reason <text>]
```

规则：

- Root/admin 可移除 scope 内任意 inspection checkout。
- Inspection token 可移除自己的 inspection checkout。
- `--dry-run` 报告 checkout path、token revocation target 和 planned trash move，不修改 DB row、不写 audit event、不删除文件。
- Inspection checkout remove 删除 inspection filesystem worktree，revoke inspection token，并将 path registry row 标记为 `removed`。
- 如果 registered inspection checkout path 已经缺失，actual checkout remove 会调和状态：revoke inspection token、将 path registry row 标记为 `removed`，并写 audit event；audit metadata 记录 filesystem path 已经不存在。
- 实际 filesystem deletion 使用与 hard remove flow 相同的 `tmp/trash/<audit_id>/` staging contract。
- Inspection checkout creation 会写 audit metadata，包含 credential type、token mode、created token id、pinned inspection commit、path registry id 和 created-for path hash。它绝不存储 raw checkout path 或 raw inspection token。
- Inspection checkout 没有 restore 命令。需要时用 `alab exp checkout` 创建新的 inspection checkout。

## 7. Run 和 Validation 生命周期

Run 命令：

```text
alab observe runs archive <run_id>
alab observe runs unarchive <run_id>
alab observe runs remove <run_id> (--dry-run|--force --confirm <run_id>) [--cascade] [--reason <text>]
```

Validation 命令：

```text
alab project validation archive <validation_id> [--project <project_id>]
alab project validation unarchive <validation_id> [--project <project_id>]
alab project validation remove <validation_id> [--project <project_id>] (--dry-run|--force --confirm <validation_id>) [--cascade] [--reason <text>]
```

规则：

- Worktree token 可以 archive 和 unarchive 自己 experiment 的 run。
- Regenerated worktree token 继承此 own-experiment run lifecycle capability，因为 permission 绑定 experiment identity，而不是特定旧 token value。
- Root/admin 可以 archive 和 unarchive project scope 内任意 run。
- Run archive/unarchive audit metadata 会记录 previous archive status、resulting archive status 和 archive/unarchive timestamp。
- Run remove 仅 root/admin 可执行，并要求 run 已 archived。
- Run remove 未传 `--cascade` 时会被 dependent artifact 或 log row 阻塞。传入 `--cascade` 后，active dependent artifact/log row 仍会阻塞 remove；已 archived 的 dependent row 会在同一个 audited transaction 中删除。
- Run cascade remove 会在 DB mutation 前使用 artifact/log reference-counted trash rules。未共享的 captured artifact blob 和 log file 会 stage 到 ALab trash；共享 physical file 保留原位。
- 删除 experiment 的 `latest_run_id` 时，要从剩余未 removed run 中重算 latest。若没有剩余 run，则 `latest_run_id` 为 `none`，`latest_commit` 保持 experiment branch HEAD。
- 删除 experiment 的 `final_run_id` 时，experiment 保持 closed，保留 final commit、summary、feedback 和 refs，并写入 `final_run_removed_at`、`final_run_removed_by` 和 `final_run_removed_audit_id`。
- Run remove audit metadata 会记录 dependent artifact/log count、active dependent count、latest run id before/after、是否删除 final run、sanitized filesystem target count、absent count、trash mode/label、target kind/object id 和 original path hash。
- Validation 生命周期仅 root/admin 可执行。
- 通过 `projects.active_validation_id` 证明 `projects.active_valid_config_version` 的 validation 不能 archive 或 remove。
- Validation archive/unarchive audit metadata 会记录 previous archive status、resulting archive status 和 archive/unarchive timestamp。
- Validation remove 未传 `--cascade` 时会被 dependent artifact 或 log row 阻塞。传入 `--cascade` 后，active dependent artifact/log row 仍会阻塞 remove；已 archived 的 dependent row 会在同一个 audited transaction 中删除。
- Validation cascade remove 会在 DB mutation 前使用 artifact/log reference-counted trash rules。未共享的 captured artifact blob 和 log file 会 stage 到 ALab trash；共享 physical file 保留原位。
- Validation remove audit metadata 会记录 dependent artifact/log count、active dependent count、sanitized filesystem target count、absent count、trash mode/label、target kind/object id 和 original path hash。

## 8. Artifact 和 Log 生命周期

命令：

```text
alab observe artifacts show <artifact_id>
alab observe artifacts archive <artifact_id>
alab observe artifacts unarchive <artifact_id>
alab observe artifacts remove <artifact_id> (--dry-run|--force --confirm <artifact_id>) [--cascade] [--reason <text>]
alab observe logs archive <log_id>
alab observe logs unarchive <log_id>
alab observe logs remove <log_id> (--dry-run|--force --confirm <log_id>) [--cascade] [--reason <text>]
```

规则：

- Worktree token 可以 archive 和 unarchive 自己 experiment 的 artifact 和 visible log。
- Regenerated worktree token 继承此 own-experiment artifact 和 visible-log lifecycle capability，因为 permission 绑定 experiment identity，而不是特定旧 token value。
- Root/admin 可以 archive 和 unarchive project scope 内任意 artifact 或 log。
- Artifact/log archive/unarchive audit metadata 会记录 previous archive status、resulting archive status 和 archive/unarchive timestamp。
- Artifact 和 log remove 仅 root/admin 可执行，并要求对象已 archived。
- Hidden log 只能由 root/admin archive、unarchive 或 remove。
- Artifact blob 和 log file 只有在没有任何剩余 row 引用同一 content 或 file 时才删除。
- Standalone artifact/log remove 会在 DB/audit mutation 前，把未共享的 blob/file 通过 hard-remove trash flow stage 到 ALab trash。共享 blob/file 会输出 `deleted filesystem paths: 0`，并保留 physical bytes。
- Artifact/log remove audit metadata 会记录 sanitized filesystem target count、absent count、trash mode/label、target kind/object id 和 original path hash。
- Archived artifact 和 log row 默认从 list 命令隐藏。
- 按 id show archived artifact/log 需要 authorization，但不要求 `--include-archived`。Export archived artifact/log 要求 authorization plus `--include-archived`。

## 9. Annotation 和 Tag 生命周期

Annotation 命令：

```text
alab annotate archive <annotation_id>
alab annotate unarchive <annotation_id>
alab annotate remove <annotation_id> (--dry-run|--force --confirm <annotation_id>) [--reason <text>]
```

规则：

- 创建 annotation 的 token、project admin 和 root 可在现有 visibility 与 ownership 规则内 archive、unarchive 和 remove annotation。
- Annotation archive tombstone annotation，但不删除 revision。
- Annotation archive/unarchive audit metadata 会记录 previous status、resulting annotation status 和 archive/unarchive timestamp。
- Annotation remove 会在同一个 audited transaction 中删除所有 revision，记录 `deleted_revision_count`，且没有 filesystem target。
- Tag 保持即时 `add`、`remove` 和 `list` 行为。Tag 没有 archive 或 unarchive 状态。

## 10. Credential、Secret、Cache、Catalog 和 Backup

Audit 规则：

- Lifecycle audit events 覆盖每个 lifecycle mutation：archive、unarchive、remove、worktree restore/remove、checkout create/remove、context repair、credential revoke/regenerate、cache prune、backup prune、secret GC、会修改 local catalog state 的 catalog add/update/remove、project lock stale-clear 删除 lock 时，以及 source/catalog/cache cleanup。
- Audit rows 使用 generic action 加 object type 模型。Valid actions 是 `add`、`update`、`archive`、`unarchive`、`remove`、`restore`、`repair`、`revoke`、`regenerate`、`prune`、`gc` 和 `clear`；object type 区分 project、source、experiment、run、validation、artifact、log、annotation、credential、secret value、cache、backup、catalog、lock、worktree 和 inspection checkout events。
- 创建 audit event 的命令成功输出应渲染 `audit id`，除非某个 command-specific secret rule 明确禁止。渲染 audit id 不得泄露 raw secret、verifier hash、hidden asset content 或 raw hidden log。
- 普通 run、submit、tag、annotation edit 和 project config/env/secret set/import/unset mutation 由各自表记录；除非有 lifecycle operation 作用于它们，否则不写 lifecycle audit row。`project secret gc --apply` 仍然 audited，因为它删除 unreferenced raw secret values。

Credential 规则：

- Root/admin key 和 experiment token 只支持 revoke 和 regenerate。
- V1 不存在 credential hard remove。
- Credential revoke/regenerate audit metadata 会记录 sanitized credential type、previous/resulting status、适用时的 revoked/created credential ids、适用时的 token mode 与 registered path hash，以及 lifecycle timestamps。它绝不存储 raw key、token、salt 或 verifier hash。
- Regenerated token 写入 registered 或 restored path，永不打印 raw token。

Secret 规则：

- `project secret unset` 只改变 active project config。
- `project secret gc --apply` 只删除没有被任何 project config version 引用的 raw secret value。

Cache 和 backup 命令：

```text
alab cache prune [--docker-images] [--skydiscover-envs] [--trash --older-than <days>|--trash-all] [--all]
alab backup prune (--keep <n>|--older-than <days>)
```

规则：

- Cache 和 backup prune 需要 root。
- Cache prune 只删除可重建 cache entry。
- `--trash --older-than <days>` 删除超过指定 age 的 trash entries。
- `--trash-all` 删除全部 trash entries。
- Top-level `--all` 包含 Docker image caches、SkyDiscover evaluator environments 和全部 trash entries。
- Backup prune 删除符合保留规则的明文 migration backup。

Catalog 命令：

```text
alab catalog skydiscover remove --force --confirm skydiscover [--reason <text>]
```

规则：

- Catalog remove 需要 root。
- 当 active project config 或任何 open experiment 的 bound config 引用 SkyDiscover catalog task 或 evaluator bundle 时，catalog remove 被阻止。
- Catalog remove 删除本地 catalog clone，并将 catalog metadata 标记为 removed。
- Catalog removal 后，closed 和 archived experiment history 必须仍可 observe，因为 safe adapter summaries、metrics、logs、artifacts 和 annotations 独立于 catalog files 存储。

## 11. Audit Visibility

命令：

```text
alab audit list [--project <project_id>] [filters]
alab audit show <audit_id> [--project <project_id>]
```

规则：

- Audit commands 不修改 project data。
- Root 可以 global list/show audit events。
- Project admin 只能 list/show 自己 project scope 内的 audit events。
- Audit output 只渲染 sanitized metadata 和 deleted id summary。
- Audit output 不得包含 raw key、token、secret value、verifier hash、hidden asset content 或 raw hidden log。
