# ALab 已关闭 Progress Guardrails

本文是 ALab V1 的 do-not-reopen guardrail list。它的目的，是让 `docs/progress.md` 和 `docs/progress_pipeline.md` 保持短小。

只有 planned work 可能重复已经关闭的 proof family 时才读本文。它不是 active backlog，也不是 evidence ledger。精确 proof 请以 `docs/completion_audit.md` 为准。

## 维护规则

- 只有 implementation evidence 已更新且 focused check 已通过后，才添加 guardrail。
- 按 behavior family 分组，不为每个单独 test assertion 建一条。
- 如果 spec 或 implementation change 使某条 guardrail 失效，更新或删除该 guardrail，并重新打开对应 audit row。
- 英文文档是 canonical；必须在同一个 change 中更新 `docs/progress_closed_gaps_cn.md`。

## Guardrail 摘要 - 2026-05-21

除非 spec 或 implementation change 推翻已记录证据，不要再为这些 families 单独开 batch：

- Runtime 和 layout guardrails：local CLI-only surface、无 server/web UI/ORM/scheduler/agent/LLM-provider dependency roots、canonical home/artifact/log layout、home/filesystem/path-registry evidence mapping、marker-only project contexts、cwd-relative experiment worktree markers，以及 128-bit home-id suffix checks。
- Runtime stack and architecture guardrails：pyproject 保持 `alab` console script、Python 3.11 floor、uv package mode、runtime dependency roots 和 dev dependency separation；`src/alab/cli.py` 暴露 Typer boundary，并把 arbitrary argv 与 `--help` 委托给 ALab pre-scan/capability logic；runtime imports 覆盖 Typer、Pydantic 和 standard-library `sqlite3`，同时 banned server/ORM/agent/LLM dependency roots 保持缺失。
- Host-support policy guardrails：blueprint/README 保持 macOS/Linux 作为 V1 host policy，Windows 继续不进入 V1 acceptance testing，当前 default-suite host 必须是 macOS/Linux，真实 Docker/SkyDiscover/Harbor behavior 继续放在 opt-in pytest markers 后。
- Documentation consistency guardrails：README/README_cn repository trees、opt-in pytest marker commands、Markdown Chinese pairs、CLI spec English/Chinese command and field synchronization、`.env.example` references、`.gitignore` local-note/env policy、progress dashboard/pipeline/guardrail/log/audit split，以及 ignored local AGENTS/CORE note alignment 都有当前 focused evidence。
- Security boundary guardrails：V1 保持 plaintext local storage、verifier-only credentials，并且没有 encrypted storage、grant-file、public-grant、token-rewrap、DEK、ciphertext、keyring 或 cryptography implementation artifacts；README/blueprint 的 collaboration-boundary 和 no-strong-local-security wording 与该实现边界保持同步。
- Parser、renderer 和 preflight guardrails：strict text object rendering、global/command option validation、payload file preflight、generated capability preflight、output alias boundaries、export-output preflight、command-specific config-value errors、complete ALab id selectors、RFC 3339 filters、`HOME_EXISTS` 和 `OUTPUT_EXISTS`。
- Public、visibility、observe 和 annotation guardrails：public safe `status`、跨 current project policy 与 stored source-experiment upper bounds 的 public `--from-exp` visibility intersection、跨 experiment list/show 与 run/artifact/log read surfaces 的 explicit token/inspection observe visibility joins、experiment 与 observe-object list filter/sort matrices、更宽 non-disclosing `SCOPE_VIOLATION` selectors、observe read/lifecycle aliases、hidden-log access/export shapes、regenerated token private-annotation rights、admin `--private-to-exp` binding、annotation target resolution，以及 annotation authorization/lifecycle。
- Source 和 experiment-state guardrails：public inline source import limits、public `--from-exp` visibility cap、Git selector abbreviation/ambiguity、source-dependent missing-path failures、source config-version hard-remove blockers 与 preserved refs、archived/closed/removed experiment command errors，以及 project secret 变化后 old experiment secret binding。
- Source import model guardrails：canonical `alab-tree-sha256-v1` manifests 会按 repo-relative path 全局排序，并包含 regular-file content hashes、executable mode、file symlink targets 和 directory symlink targets；standalone remote `--source-git --source-subdir` imports 会持久化 resolved-commit metadata，不泄露 raw URL/path，并使用 filtered subdir tree hash。
- Experiment create source-binding guardrails：default-source creation、inline local/Git/empty/subdir imports、source dedupe、archived source `--source-ref` admin binding、public no-key 和 admin inline-source policy、`--from-exp` latest/final/best/SHA resolution、mutable override narrowing、token file creation without raw-token rendering，以及 selector/preflight no-write failures 都有直接证据。
- Run/submit lifecycle guardrails：local/default run 和 submit paths 覆盖 parser preflight、project/experiment/worktree state blockers、operation locks、stale running-row interruption、invalid Git states、running-row-before-auto-commit ordering、mutable-scope rollback/metadata、contextless runner workspaces、final-run success/failure behavior、summary/feedback/ref input rules、secret-value rejection，以及 failed/timeout/error runs 不写 final-submission rows。
- Lifecycle 和 hard-remove guardrails：registered archive/unarchive/remove surfaces 已映射到 direct evidence；project、source、validation、experiment、run、artifact、log、annotation、worktree 和 inspection checkout surfaces 的 stable dry-run/force/confirm blockers；source/validation remove audit actor/cascade 和 metadata rows；source ref deletion 与 archived dependent experiment history retention；reference-counted artifact/log trash staging；validation/run shared blob deletion；当前 run-removal paths 的 latest/final run remove metadata；project/experiment hard-remove retained `path_registry` 和 credential rows 以及 audit actor alignment。
- Context marker guardrails：symlink aliases 会解析到 registered context；missing markers 返回 `CONTEXT_NOT_FOUND`；invalid JSON、home-id mismatch 和 registry disagreement 返回 `CONTEXT_CONFLICT`；这些 failure paths 不改变 path registry rows，也不写 repair audits。
- Context repair guardrails：worktree self-repair 会在 old registered path 仍存在时拒绝 duplicate targets 且不改变 registry/audit；moved experiment worktrees 需要 registered branch 才能 self-token repair；moved inspection checkouts 需要 pinned inspection commit，mismatch 时会保留 registry/audit state，成功 self-token repair 后记录 token-actor repair metadata。
- Credential model guardrails：malformed credentials、unknown ids、type-prefix/type-row mismatches、revoked rows、verifier mismatches、required-scope mismatches、project mismatch、token-mode mismatch 和 token-path mismatch 都以 generic `AUTH_DENIED: invalid credential` 失败；raw credential secrets 和 salts 使用文档规定的 `secrets` byte counts；project admin keys 保持 project-scoped，不能管理 credentials。
- Credential/token side-effect guardrails：token regenerate/revoke paths 已有 audit metadata、raw-token non-rendering、old/new credential status changes、marker token-id update、raw token rotation 和 private annotation continuity 的直接证明。
- Maintenance object audit guardrails：backup/cache prune、lock clear 和 catalog remove audit rows 带有 actor credential ids、generic action/object ids、cascade flags、适用处的 reason，以及 schema-versioned metadata；cache trash 与 Docker warning branches 记录 prune/warning counts；catalog removal 在删除 local checkout 后仍保留 catalog-independent experiment/run/log history。
- Credential audit guardrails：root credential regenerate 和 admin key create/revoke audit rows 带有预期 actor credential ids、generic action/object ids、cascade flags、schema-versioned metadata、适用处的 revoked credential references，并且不包含 raw root/admin keys。
- Reward、artifact 和 log capture guardrails：exit-code/file/stdout-regex/Harbor/SkyDiscover reward parsing、saved reward-parse failures、artifact root 与 symlink containment、directory expansion/sort/deduplication、skipped/error/oversized artifact rows、log redaction/truncation/storage/export、hidden adapter streams，以及 shared log file reference deletion。
- Runner cleanup guardrails：local、Docker、Harbor、SkyDiscover Python 和 SkyDiscover Docker default/fake paths 会清理 operation temp dirs、避免修改 visible worktree、strip credentials、在适用处关闭 stdin、timeout 时移除 named Docker containers，并保存 non-pass tails 且不泄露 hidden logs。
- Project config/schema guardrails：normalized path escapes、Docker image/Dockerfile/context mutual requirements、host-network rejection、unsupported platform selector rejection 与 Linux alias canonicalization、raw Docker passthrough rejection、build/env string-map strictness、adapter ref requirements、reward-type required fields、capture limit shapes、visibility/public-source policy shapes，以及 saved source-dependent runner/reward/Dockerfile/context failures。
- Project config edit-semantics guardrails：latest-attempted edits、runtime baseline triggers、invalid-runtime preservation of the previous active valid config、byte-identical no-op edits、metadata-only inherited versions、monotonic revert versions，以及 config set/import dry-runs 都有直接 smoke evidence，并证明 dry-run 不写 config/validation/audit/project-pointer。
- Project init precedence guardrails：local/Git/empty mode-specific origins、duplicate init options、source-ref mismatch、init-time source limit failures、malformed/negative limit values、short-transaction no-row/no-staging behavior before write、baseline failure 后 retained invalid projects、one-time admin key rendering，以及 adapter-derived editable-source precedence/conflict/fallback paths 都有直接证据。
- Global config capability-refresh guardrails：`config validate --refresh-capabilities` 会在 fake/default probes 下清空并重建 Docker capability rows，buildx 不可用时记录 native-platform fallback，并为 platform/resource pre-write rejection 提供证据；真实 daemon 行为仍属于 opt-in。
- Harbor guardrails：对 multi-step tasks、non-Linux OS/platform、GPU fields、storage、MCP servers、healthchecks、custom scheduling、external services、Compose/multi-container runtime、host environment placeholders、raw Docker args 和 task-declared host mounts 的 strict unsupported-field 与 placeholder validation；shared/separate verifier default/fake execution with hidden logs。
- SkyDiscover catalog/source guardrails：exact pinned commits、ref resolution 期间不 auto-update、dirty catalog update rejection、unexpected remote rejection、active-config 与 open-experiment removal blockers、dependencies close 后 successful removal、catalog-independent historical observability、source precedence、`--source-ref` rejection、initial program import、missing-initial failure、explicit source hash-conflict rejection，以及没有 initial program 时 explicit Git/empty source success。
- Public Git inline-source guardrails：隔离的 global Git credential helper 已配置时，public `--source-git` 会渲染 `PUBLIC_GIT_CREDENTIAL_HELPER_USED`；global/system Git configs 都没有 helper 时不渲染 helper warning；并持久化匹配的 source-origin warning metadata。
- SkyDiscover evaluator guardrails：Docker evaluator feedback/file-artifact separation、fake/default paths 下的 Docker evaluator hidden bundle 与 timeout cleanup、Python evaluator hidden bundle、wrapper-subprocess import boundary、non-sandbox disclosure、dependency-installation saved failures、hidden setup logs，以及 default/fake paths 下无 debug traceback。

## 最近关闭

- 2026-05-21：host-support policy proof，覆盖 macOS/Linux-only V1 host support、Windows exclusion、当前 Darwin default-suite host 和 opt-in real runner markers。
- 2026-05-21：final default-suite closeout gate，覆盖 home/filesystem 与 host-support evidence-map batch 后的当前 worktree。
- 2026-05-21：home/filesystem/path-registry evidence mapping，覆盖 home resolution/layout、path-registry hash/reuse、context marker conflict contracts，以及 worktree/checkout/repair paths。
- 2026-05-21：lifecycle archive/unarchive/remove row-by-row evidence mapping，覆盖每个当前 registered archive/unarchive surface，以及每个当前 registered hard-remove/cleanup remove surface，immediate tag removal 例外。
- 2026-05-21：runtime stack and architecture proof，覆盖 Typer entrypoint delegation、pyproject stack contracts、runtime imports、无 ORM/server/agent dependency drift，以及 Rich non-persistence。
- 2026-05-21：documentation consistency proof，覆盖 README/README_cn、Markdown pair coverage、CLI spec synchronization、`.env.example`、`.gitignore`、progress/audit ledgers，以及 ignored local AGENTS/CORE notes。
- 2026-05-21：当前 default/fake runner types 的 shared-runner cleanup 和 adapter failure edges。
- 2026-05-21：当前 schema/default source-dependent paths 的 project config/schema proof mapping。
- 2026-05-21：project config edit semantics proof mapping，覆盖 latest-attempted base、no-op edits、metadata-only inherited edits、monotonic revert versions、invalid-runtime preservation 和 dry-run no-write behavior。
- 2026-05-21：project init input precedence proof mapping，覆盖 mode-specific origins、source-ref injection/mismatch、short-transaction write ordering、malformed/exceeded limit failures、retained invalid project baseline failures 和 adapter-derived editable-source bootstrap paths。
- 2026-05-21：source import canonical tree-hash 和 standalone remote-Git fidelity proof，覆盖 manifest ordering/entries、symlink handling、resolved commit metadata、sanitized origin metadata、filtered subdir contents 和 stored tree hash。
- 2026-05-21：experiment create source-binding/default-source proof mapping，覆盖 inline sources、default sources、archived source refs、public import policy、`--from-exp` commit selectors、mutable override narrowing、token non-rendering 和 selector-conflict no-write behavior。
- 2026-05-21：run/submit lifecycle proof mapping，覆盖 local/default run 和 submit parser/state/lock/Git/mutable-scope/running-record/final-submission behavior。
- 2026-05-21：project/experiment hard-remove retained-row relationships，覆盖 removed `path_registry` rows、revoked credentials、deleted primary rows 和 audit actor alignment。
- 2026-05-21：public `--from-exp` visibility-intersection behavior，覆盖 `none`、`same_project`、current explicit project lists 和 source-experiment explicit upper bounds。
- 2026-05-21：source/validation hard-remove audit 和 reference relationships，覆盖 config-version source blockers、source Git ref deletion metadata、archived dependent experiment retention、validation child deletion metadata，以及 admin actor/cascade audit rows。
- 2026-05-21：maintenance object audit metadata relationships，覆盖 backup prune、cache prune、stale lock clear 和 SkyDiscover catalog remove rows。
- 2026-05-21：credential audit metadata relationships，覆盖 root regenerate 和 admin key create/revoke rows，包括 actor/action/object/cascade metadata 以及 raw-key absence。
- 2026-05-21：credential model proof mapping，覆盖 generic auth-denial failures、high-entropy secret/salt source usage 和 project-admin key-management authority boundaries。
- 2026-05-21：inspection context repair pinned-commit 和 audit metadata relationships，覆盖 moved inspection checkout self-repair。
- 2026-05-21：context repair old-path-still-exists blocker，覆盖 worktree self-repair 且不改变 registry/audit。
- 2026-05-21：token revoke/regenerate side-effect evidence mapping，覆盖 audit metadata、token status、marker update、raw token rotation 和 private annotation continuity。
- 2026-05-21：context marker conflict 和 symlink-alias mapping，覆盖 missing marker、invalid JSON、home mismatch、registry disagreement 和 side-effect-free failures。
- 2026-05-21：explicit token/inspection observe visibility joins，覆盖 current project explicit lists、own-experiment retention、peer experiment/run/artifact/log reads，以及 non-disclosing unlisted experiment failures。
- 2026-05-21：run/artifact/log/annotation observe list filter/sort matrices，覆盖当前 default local visible/admin paths 的 scoped filters、range filters、archive inclusion、sort whitelists 和 run reward null-last ordering。
- 2026-05-21：experiment list/search/best filter、pagination 和 sort matrices，覆盖当前 default local visible/admin paths 的 repeated tag AND semantics、multi-source source-id filtering、status/time/name/reward/config filters、archive inclusion、experiment sort whitelists、best pagination 和 reward null-last ordering。
- 2026-05-21：V1 plaintext/security-boundary negative proof，覆盖 absent encryption/grant/rewrap dependency、import、source、migration artifacts，以及 README/blueprint boundary wording。
- 2026-05-21：global config capability-refresh proof mapping，覆盖 fake/default Docker capability cache refresh、native-platform fallback 和 platform/resource pre-write rejection evidence。
- 2026-05-21：public `--source-git` credential-helper warning proof，覆盖 helper-available 和 helper-unavailable paths。

## 仍在别处 Active

不要把本文视为 completion claim。Active queue 仍在 `docs/progress_pipeline.md`；精确 open evidence 仍在 `docs/completion_audit.md`；历史 implementation records 仍在 `docs/progress_log.md`。
