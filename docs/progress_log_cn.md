# ALab 实现进展日志

本文是 ALab V1 的历史 implementation journal。请先阅读 `docs/progress.md` 获取当前 dashboard，再阅读 `docs/progress_pipeline.md` 获取 active queue。只有 planned work 可能重复已关闭 proof family 时才使用 `docs/progress_closed_gaps.md`。下面较早的 `尚未完成` 条目只保留历史含义，除非被提升到 `docs/progress_pipeline.md`。

## 维护规则

- 只有在已更新 `docs/progress_pipeline.md`，并在 gate-level status 改变时更新 `docs/progress.md` 后，才在这里追加详细 batch entry。
- Entry 保持简洁：implemented behavior、verification 和 residual risk。
- 不要把本历史日志当成当前 backlog；`docs/progress_pipeline.md` 才是下一步工作的当前 source of truth。
- 修改英文 `docs/progress_log.md` 时，必须在同一个 change 中更新本文件。

## 详细实现日志

## 2026-05-17 第一阶段可运行里程碑

已实现：

- 带 `pyproject.toml`、`src/alab/`、tests 和 `alab` entry point 的 Python package scaffold。
- Strict text renderer、稳定 error rendering、global option pre-scan、command registry、context-aware help 和 command preflight。
- ALAB home layout、SQLite WAL schema、root/admin/token HMAC verifier storage、context marker detection、path registry 和 audit event foundation。
- 从 local/Git/empty source 初始化 local project、source snapshot ref、baseline validation、local runner execution、log/artifact storage foundation、experiment worktree creation、run、submit、基础 status/list/observe runs 和 audit list。
- 覆盖 auth init/config show 以及 local project -> experiment -> run -> submit workflow 的 smoke tests。

尚未完成：

- 所有对象的完整 lifecycle maintenance。
- 完整 observe filters/search/best ranking、annotation、inspection checkout 和 project config mutation。
- Project init 之后的 source import mutation、cache/catalog/backup workflows，以及 Docker/Harbor/SkyDiscover adapters。
- `docs/spec_tests.md` 要求的完整 CLI golden matrix。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- 使用临时 `ALAB_HOME` 手动 smoke：`auth init`、`project init local`、`exp create`、`run` 和 `submit`。

## 2026-05-17 本地 Workflow 扩展

已实现：

- Project config show/export/import/set、metadata-only inherited config version、runtime-affecting baseline validation，以及手动 `project validate`。
- Project env set/unset/list 和 project secret set/unset/list。Raw secret value 仍是本地 plaintext storage，但不会被渲染或 export；export 使用 retain marker。
- Init 后 local/Git/empty source snapshot 的 source import/show/list/archive/unarchive/remove dry-run，包括 active-source tree dedupe。
- 本地可见 record 的 observe run show/archive/unarchive/remove、artifact list/show/export/archive/unarchive/remove，以及 log list/show/export/archive/unarchive/remove。
- Project 和 experiment archive/unarchive，以及受 dry-run 和 confirmation 保护的 remove command。
- Admin/root key 和 owning experiment worktree token 可使用 experiment tag add/remove/list。
- Audit show 和 audit list filters。
- 扩展 smoke tests，覆盖 config export/set、init 后 source import、token-scoped tags、log export 和 artifact export。

尚未完成：

- Lifecycle remove 仍需要完整 V1 trash staging、完整 blocker coverage 和更细的 cascade accounting。
- Observe visibility 目前保守实现为 root/admin project scope 与 owning experiment token scope；完整 same-project/explicit visibility search 和 best ranking 仍待实现。
- Annotation、inspection checkout、worktree restore、experiment token maintenance、project validation lifecycle maintenance、cache/catalog/backup workflows，以及 Docker/Harbor/SkyDiscover adapters 仍待实现。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-17 协作 Context 扩展

已实现：

- Experiment worktree remove/restore，包括 path registry 更新、active worktree token revoke、新 worktree token 创建、marker rewrite 和 audit event。
- Worktree 与 inspection 两种 token mode 的 experiment token list/revoke/regenerate。Regenerate 会把新的 raw token 写入 registered path，但不会渲染 raw token。
- Inspection checkout create/remove。Inspection context 会得到 detached Git worktree、inspection marker、scoped inspection token，以及只读 CLI observe access。
- Annotation add/edit/archive/unarchive/remove，以及 observe annotations list/show。当前实现支持 experiment/run/artifact target 和常用 experiment-context path/line shorthand、revision history、project/private visibility，以及 annotation body 的 secret-value 拒绝。
- Smoke coverage 覆盖 token listing/regeneration、inspection checkout observe/remove、annotation add/edit/show/archive/remove dry-run，以及 worktree remove/restore。

尚未完成：

- Annotation branch-name commit resolution 和 file/line Git validation 已由后续 progress entry 覆盖。
- Observe visibility 和 search/best ranking 已由后续 progress entry 覆盖。
- Worktree 和 checkout trash staging 语义已由后续 progress entry 覆盖。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`

## 2026-05-17 Observe Experiment 扩展

已实现：

- `exp search`、`exp show`、`exp best` 以及对应 `observe experiments search/show/best` alias 现在使用与 `exp list` 相同的结构化 experiment result block。
- Experiment list/search/best 支持 pagination、status/tag/source/name/time/config-version filters、reward min/max filter、基础 sort fields，并可在 experiment metadata、tag、project task text、final submission text 和 latest annotation body 中做大小写不敏感搜索。
- Best ranking 每个可见 experiment 最多选一个 parsed passed run，遵守 reward direction，默认排除 archived run，并在默认 active-valid policy 情况下使用 reward-policy identity comparison。
- Token observe visibility 现在计算当前 project visibility policy 与 source experiment 创建时存储的 visibility upper bound 的交集。Token 永远可见自己的 experiment；只有两个 policy 都允许时才可见 same-project 或 explicit peer experiment。
- Runs、artifacts、logs、annotations、checkout target resolution 和 annotation target resolution 现在共享同一个 visible-experiment calculation，不再硬编码为 own-experiment-only observe access。
- Smoke coverage 现在覆盖 same-project token visibility、experiment search、experiment show，以及两个 experiment worktree 之间的 reward-ranked best selection。

尚未完成：

- Best warning details 已在后续 Best Incomparable Warning 章节实现。
- Runs/artifacts/logs/annotations 的 observe filters 仍需补齐文档中的完整矩阵。
- Public from-experiment inheritance 记录在后续 Public From-Experiment Inheritance 章节中。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-17 Context Repair 扩展

已实现：

- `context show` 现在会渲染当前或指定路径的 marker 与 path-registry 状态，包括 registered 状态以及 present/moved/conflict/unregistered path status。
- `context repair --path <dir>` 现在可修复 project、experiment 和 inspection marker 的 path registry entry。它支持 root/admin credential，也支持 previous registered path 已不存在时的 matching self-token repair。
- Repair 会更新 registry path/hash data，向 marker metadata 写入 `repaired_at`，并使用现有 object type 写入 audit event。
- Smoke coverage 验证 experiment worktree 内的 context show 和 admin repair。

尚未完成：

- Self-token repair Git checks 已在后续 Context Self-Repair Git Checks 章节实现。
- Repair 当前直接更新 registry state；完整 V1 lifecycle/trash 语义仍是独立待办。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-17 Credential 与 Validation Lifecycle 扩展

已实现：

- `key create`、`key list` 和 `key revoke` 现在可管理 root/admin credential row，并且不存储 raw key material。`key create` 只打印一次生成的 raw admin key。
- `project validation archive`、`project validation unarchive` 和 `project validation remove` 现在支持 admin/root 对非 active project validation row 做 lifecycle maintenance。
- Validation remove 支持 dry-run、confirmation、validation log/artifact 的 cascade deletion、active/running/not-archived validation blocker，以及 lifecycle audit event。
- TOML export 现在会在调用 `tomli-w` 前移除 optional `None` 字段，匹配官方依赖行为，不再依赖 fallback serialization。
- Smoke coverage 现在覆盖 key creation/list/revoke 和 validation archive/unarchive/remove。

尚未完成：

- Validation remove 的 reference counting 和 trash staging 已在后续 Validation Remove Reference-Counted Trash 章节实现。
- 更广的 local maintenance command 和 SkyDiscover catalog lifecycle command 记录在后续进展章节中。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`

## 2026-05-17 Docker Runner 扩展

已实现：

- 新增统一 `run_configured_runner` 边界。本地 validation/run workflow 仍使用 local subprocess 路径，Docker config 现在通过同一个 runner result model 执行。
- Docker runner 现在支持 explicit `runner.image` 和 `runner.dockerfile` 加 `runner.context` config、`runner.command` 或 `runner.shell`、workspace 挂载到 `/app`、run directory 挂载到 `/logs/alab`、container-visible ALab env，以及 `runner.network = "default"|"none"`。
- 配置的 image 缺失时会触发 `docker pull`；Dockerfile config 会根据 Dockerfile 内容、`.dockerignore`、有效 build context bytes、build args、target 和 platform 计算 ALab-owned cache key，并把 image tag 为 `alab-cache:<digest>`。
- Dockerfile cache metadata 会写入 `cache_entries`，因此现有 `cache prune --docker-images|--all` 可以看到 ALab-owned image cache row。
- 新增不需要 live Docker daemon 的 Docker runner unit/contract coverage：`.dockerignore` cache-key 行为、workspace escape rejection、fake-Docker run contract，以及结构化 not-implemented adapter error。

尚未完成：

- Docker capability probe、image cache pruning 和 pre-write resource check 记录在后续 Docker Capability 与 Cache-Prune 扩展章节中。
- 更细的 per-architecture Docker platform specificity 仍待实现。
- Harbor 和 SkyDiscover adapter 已由 config schema 表达或注册，但 runner 尚未实现。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`

## 2026-05-17 Local Maintenance 扩展

已实现：

- `project secret gc --apply` 会删除未被引用的 raw secret value，并写入 lifecycle audit event。不带 `--apply` 时只报告当前未引用集合，不删除数据。
- `project locks clear-stale` 会删除过期 project lock，并报告 cleared lock name。
- `backup prune --keep <n>|--older-than <days>` 会清理 `ALAB_HOME/backups` 下的本地 migration backup file。
- `cache prune` 现在会验证 V1 selector combination，并将匹配的 rebuildable cache row 标记为 removed；对 ALab-owned cached path 执行安全路径删除。
- Smoke coverage 现在验证零计数 secret GC、stale lock clearing，以及通过 root credential 执行 backup prune 和 cache prune。

尚未完成：

- Docker image cache removal 记录在后续 Docker Capability 与 Cache-Prune 扩展章节中；SkyDiscover environment cleanup 记录在后续 SkyDiscover Python Runner 扩展章节中。
- Backup prune 会直接删除匹配文件；完整 migration backup creation/checksum coverage 仍待实现。
- SkyDiscover catalog add/update/show/remove 记录在后续 SkyDiscover Catalog 扩展章节中。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`

## 2026-05-17 SkyDiscover Catalog 扩展

已实现：

- 将剩余 catalog stub 替换为需要 root credential 的 `catalog skydiscover add/update/show/remove` handler。
- `add` 会将选定 origin clone 到 `ALAB_HOME/sources/skydiscover`，把 `--ref`、`--commit` 或 upstream `main` 解析为 exact pinned commit，checkout 到该 commit，存储 catalog metadata，并写入 lifecycle audit event。
- `update` 会验证本地 catalog 是 clean Git repository，从选定 origin refresh，pin exact commit，更新 metadata，并记录 audit。
- `show` 只读取本地 SQLite state，渲染 active catalog，不从网络 fetch。
- `remove` 要求 `--force --confirm skydiscover`，会阻止仍被 active project config/open experiment 引用的 `skydiscover:` 字符串，删除 `ALAB_HOME/sources` 下的本地 catalog path，将 metadata 标记为 removed，并写入 audit。
- Config validation 现在会针对 Harbor-compatible task ref 与 SkyDiscover Docker/Python evaluator ref，把 `skydiscover:<path>` ref 解析到 active pinned catalog，且不会 auto-fetch。
- Smoke coverage 使用本地 Git upstream，因此 catalog add/update/show/remove 和 catalog-ref validation 测试不依赖网络。

尚未完成：

- Catalog URI resolution 已接入 project init 和 project config import/set。Python evaluator materialization 与 runner execution 记录在后续 SkyDiscover Python Runner 扩展章节中；Docker evaluator execution 记录在后续 SkyDiscover Docker Runner 扩展章节中。
- 从 benchmark metadata 执行 SkyDiscover initial editable-source bootstrap 记录在后续 Adapter-Derived Source Bootstrap 章节中。
- `update --origin-url` 支持在验证当前本地 repository 后切换 origin，但更深入的 upstream trust 与 dirty-state diagnostics 仍较基础。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Docker Capability 与 Cache-Prune 扩展

已实现：

- `config validate --refresh-capabilities` 现在会 probe Docker availability、Linux container platform reporting，以及 `docker run` CPU/memory flag support，并把安全诊断 row 写入 `runtime_capabilities`。
- Docker capability row 按 runtime fingerprint 缓存；fingerprint 未变化时复用缓存。Refresh 会先清除 cached Docker row，再重新 probe。
- `runtime_capabilities.status` 对新 home 已加入文档要求的 `supported|unsupported|error` check。
- Project init 和 project config import/set 现在会查询 cached Docker probe，并在写入 project config version 前拒绝 unsupported configured `runner.platform`、`runner.cpus` 或 `runner.memory_mb`。Docker availability error 仍进入保存的 baseline/run record，不阻止 config persistence。
- `cache prune --docker-images` 现在会先用 `docker image rm` 删除 ALab-owned Docker image tag，再把 cache row 标记为 removed。如果 Docker cleanup 失败，row 保持 active，并输出 `DOCKER_CACHE_PRUNE_FAILED` warning block。
- Docker runner tests 现在通过 fake Docker CLI 覆盖 capability refresh persistence、pre-write resource-limit rejection 和 ALab-owned image removal，仍不需要 live Docker daemon。

尚未完成：

- Docker platform enforcement 在本切片中有意保持粗粒度：报告为非 Linux container runtime 时会阻止 configured `runner.platform`，但 per-architecture/platform matrix probing 仍待实现。
- Harbor runner execution 记录在后续 Harbor Runner 扩展章节中。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 SkyDiscover Python Runner 扩展

已实现：

- `run_configured_runner` 现在通过与 local/Docker runner 相同的 structured runner result model 支持 `runner.type = "skydiscover_python"`。
- SkyDiscover Python evaluator ref 会在 validation/run 时针对 active pinned catalog 解析，然后复制到 editable workspace 和 run directory 之外的 hidden staging bundle。
- Evaluator code 通过 ALab wrapper 子进程执行。主 ALab 进程不会 import evaluator code；visible stdout 是安全 summary，包含 task ref、pinned commit、evaluator mode、metric names、reward，以及明确的 `not-os-sandbox` 提示。
- Raw evaluator stdout/stderr 和 wrapper failure traceback 会存入 hidden log stream；写入存储前会按 configured secret bytes 进行 redaction。
- Evaluator 返回数据会拆分为 structured metrics 和 adapter feedback。SkyDiscover reward parsing 使用 configured primary metric；当默认 `combined_score` 缺失时，会 fallback 到有限 numeric top-level metric 的平均值。
- Python dependency manifest 会在 `ALAB_HOME/cache/skydiscover-python-envs` 下创建或复用 ALab-managed `uv` environment。Cache row 现在会存储 environment path，`cache prune --skydiscover-envs|--all` 会安全删除这些路径。
- 新增 direct runner coverage，覆盖 hidden bundle materialization、hidden stdout capture、metric/reward parsing 和 fake-`uv` environment cache reuse。新增 smoke test，覆盖 catalog-backed baseline validation 的 metrics 与 hidden logs 入库。

尚未完成：

- SkyDiscover Docker evaluator execution 记录在后续 SkyDiscover Docker Runner 扩展章节中。
- 从 benchmark metadata 执行 SkyDiscover initial editable-source bootstrap 记录在后续 Adapter-Derived Source Bootstrap 章节中。
- Python evaluator 有意不作为 OS sandbox；当前实现会在 visible summary 中明确说明这一点，但除 subprocess execution 外不提供额外 process isolation。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 SkyDiscover Docker Runner 扩展

已实现：

- `run_configured_runner` 现在通过与 local、Docker、SkyDiscover Python runner 相同的 structured runner result model 支持 `runner.type = "skydiscover_docker"`。
- SkyDiscover Docker evaluator ref 会在 validation/run 时针对 active pinned catalog 解析，然后复制到 editable workspace 和 run directory 之外的 hidden staging bundle。
- Evaluator Dockerfile 会构建为 ALab-owned `alab-cache:<digest>` image tag，并写入 cache row。Cache key 包含 hidden bundle build inputs 和白名单 build settings。
- Evaluator run 会把 candidate workspace mount 到 `/workspace`、run output mount 到 `/logs/alab`、hidden evaluator bundle 以 read-only 方式 mount 到 `/alab/evaluator`，然后通过 `/bin/sh` 执行 `/alab/evaluator/evaluate.sh`。
- Raw evaluator stdout/stderr 和 Docker build/setup output 会存入 hidden log stream；写入存储前会按 configured secret bytes 进行 redaction。
- Evaluator stdout 会按 JSON 解析，拆分为 structured metrics 和 adapter feedback；`artifacts` JSON 只保留在 feedback 中，不会变成 file artifact rows，除非常规 artifact glob 捕获了文件。
- 新增 direct fake-Docker runner coverage 和 catalog-backed smoke baseline test，覆盖 hidden bundle staging、hidden mount separation、metric/reward parsing、feedback artifacts JSON、hidden logs 和 Docker image cache rows。

尚未完成：

- Harbor runner execution 记录在后续 Harbor Runner 扩展章节中。
- 从 benchmark metadata 执行 SkyDiscover initial editable-source bootstrap 记录在后续 Adapter-Derived Source Bootstrap 章节中。
- Docker platform enforcement 仍较粗粒度，还需要更深入的 per-architecture/platform probing。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Harbor Runner 扩展

已实现：

- `run_configured_runner` 现在通过与 local、Docker、SkyDiscover runner 相同的 structured runner result model 支持 `runner.type = "harbor"`。
- Harbor task ref 可以指向本地 task directory，也可以指向解析为 Harbor-compatible task 的 `skydiscover:<path>` catalog ref。
- Harbor task validation 覆盖 strict V1 subset：`task.toml`、`tests/test.sh`、shared environment image 或 `environment/Dockerfile`、separate verifier image 或 `tests/Dockerfile`、Linux-only execution，并对 multi-step、Windows/non-Linux、GPU、storage、MCP、healthcheck、services、Compose、raw Docker passthrough、host mounts 和 placeholder values 严格失败。
- Harbor literal task environment values 会作为 secret environment values 注入 verifier execution，并参与 exact-byte log redaction。
- Harbor verifier 会物化到 editable workspace 和 run directory 之外的 hidden bundle。Docker run 会把 candidate workspace mount 到 `/workspace`、run output mount 到 `/logs/alab`、hidden Harbor bundle 以 read-only 方式 mount 到 `/alab/harbor`。
- Harbor reward parsing 会读取 `run:/logs/verifier/reward.json` 或 `run:/logs/verifier/reward.txt`；JSON reward 会填充 structured metrics，并使用 `reward.primary_metric`，默认 `reward`。
- Verifier Dockerfile 会构建为 ALab-owned `alab-cache:<digest>` image tag，并写入 cache row。Task `environment.allow_internet=false`、`environment.cpus` 和 `environment.memory_mb` 会映射到 Docker run settings，除非被 config 覆盖。
- 新增 direct fake-Docker Harbor runner coverage，覆盖 shared verifier execution、hidden log redaction、network/resource mapping、hidden bundle mounts 和 unsupported-field rejection。新增 smoke baseline test，覆盖使用本地 Harbor task ref 的 project init。

尚未完成：

- 从 task `source` metadata 执行 Harbor adapter-derived editable-source bootstrap 记录在后续 Adapter-Derived Source Bootstrap 章节中。
- `instruction.md` 到 project task metadata 的 Harbor task text precedence 已在后续 Adapter-Derived Source Bootstrap 章节实现。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Adapter-Derived Source Bootstrap

已实现：

- `project init harbor` 现在会从 supported Harbor task `source` metadata 推导 editable default source。source path 必须是 task-relative、位于 task directory 内、真实存在，并避开 `tests/`、`environment/`、`solution/` 等 verifier/private top-level path。
- 没有 supported editable source 的 Harbor task，在 caller 未提供 explicit source selector 时会 fallback 到 empty source。这符合 V1 Harbor fallback rule，且除非显式 skip，仍需要 baseline validation。
- Harbor `instruction.md` 现在只会在 ALab config task 为空且 caller 未提供 `--task` 时成为 visible project task text；explicit config 或 CLI task text 仍优先。
- `project init skydiscover` 现在会从 SkyDiscover benchmark metadata（`benchmark.toml`、`metadata.toml`、`skydiscover.toml` 或对应 JSON 文件）或保守的 conventional starter 名称（如 `initial_program`、`starter`、`program.py`）推导 editable default source。
- SkyDiscover 只导入 initial program file 或 directory，绝不整体导入 benchmark directory、evaluator files、private data 或 dependency manifest。没有 initial program 且未提供 explicit source selector 时，init 以 `SOURCE_INVALID` 失败，并要求提供 explicit source。
- Adapter init 现在会在 explicit caller source 与 adapter-derived source 同时存在时比较 canonical ALab tree hash。tree 一致则 dedupe；不一致会在写入 project rows 前失败。
- Source origin metadata 记录 safe adapter summary 和 relative source path，不存 hidden asset bytes 或 evaluator/verifier 内容。
- 新增 smoke coverage，覆盖 Harbor declared-source import、adapter explicit-source conflict rejection、SkyDiscover metadata initial-program import，以及 SkyDiscover missing-initial failure。

仍未完成：

- Docker platform specificity 已由后续 Docker platform native fallback 里程碑覆盖。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -k "harbor_project_init_uses_declared_source or adapter_init_rejects_conflicting_explicit_source or skydiscover_project_init_uses_initial_program_metadata or skydiscover_project_init_requires_initial_program_without_explicit_source"`
- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-17 Public From-Experiment Inheritance

已实现：

- `alab exp create --from-exp <exp_id>` 现在会从 existing experiment commit 创建新 experiment worktree，而不是创建新的 source row。
- Public no-key inheritance 会被 current project visibility policy 与 source experiment stored visibility upper bound 的交集限制。Public caller 只能继承可见的 open/closed experiment；archived source experiment 需要 root/admin。
- Token-context caller 只能继承 token-visible open/closed experiment。Root/admin caller 也可以继承 archived experiment。
- `--from-commit latest` 会优先解析 source experiment latest run commit，没有 run 时解析 source experiment branch HEAD。`final`、`best` 和 explicit reachable commit selector 已支持；缺失 final/best commit 或 commit 不可达会稳定失败。
- 新 experiment 会通过 source experiment 的 `source_id` 存 source lineage，把 resolved inherited commit 存为 `baseline_commit`，并在 experiment metadata 中保存 `creation_origin.kind = "from_exp"` selector。
- 新增 smoke coverage，覆盖 public 从 latest commit 继承，以及 public visibility-upper-bound rejection。

仍未完成：

- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -k "public_exp_create_from_exp_uses_latest_commit or public_from_exp_respects_visibility_upper_bound"`
- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Public Inline Source Import

已实现：

- `alab exp create --source-path|--source-git|--source-empty` 现在会在创建 experiment worktree 前执行 inline source snapshot import。
- Inline import 与 standalone `alab source import` 共用 snapshot commit、canonical tree hash、active-tree dedupe、source metadata、Git submodule rejection 和 audit 路径。
- Public no-key caller 受 `[public_source_import]` 限制；命令行可以降低 limit，但不能超过 project policy。Root/admin inline import 使用 normal source import default，并可像 standalone import 一样覆盖 limit。
- 通过 inline import 创建的新 experiment 会在 metadata 中记录 `creation_origin.kind = "inline_source"`，并绑定 imported 或 deduped source id。
- 新增 smoke coverage，覆盖 public inline source creation，以及 public policy limit rejection 且不泄漏 source row。

仍未完成：

- Remote public Git import 仍需要文档中的 credential-helper warning surface。
- Local source fidelity 相比完整 Git-aware `.alabignore`/tracked-file rules 仍是简化实现。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Local Source Fidelity

已实现：

- Local path source import 现在会检测 selected path 是否位于 Git worktree 内，并从当前 filesystem state 导入 tracked files 加 untracked Git-nonignored files。
- Tracked files 即使匹配 built-in sensitive excludes 或 root `.alabignore` 也会导入；source result 会输出 `TRACKED_SENSITIVE_SOURCE_FILE`。
- 匹配 Git ignore rules、root `.alabignore` 或 built-in sensitive excludes 的 untracked files 会被过滤。
- Non-Git directory import 现在会在 snapshot 前应用 root `.gitignore`、root `.alabignore` 和 built-in sensitive excludes。
- 过滤成 empty tree 现在会成功并输出 `SOURCE_EMPTY_AFTER_FILTER`；显式 `--source-empty` 仍不产生 warning。
- 新增 smoke coverage，覆盖 Git tracked sensitive files、untracked `.gitignore`/`.alabignore` filtering，以及 empty-after-filter source import。

仍未完成：

- 未安装 `pathspec` 时使用的 fallback ignore matcher 有意比 dependency-backed GitWildMatch implementation 简化。
- Remote public Git import 仍需要文档中的 credential-helper warning surface。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py -k "source_import_respects_git_and_alab_ignore_rules or source_import_empty_after_filter_warns" -q`
- `/opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Worktree 和 Checkout Trash Staging

已实现：

- `exp worktree remove` 现在会先把 registered worktree path stage 到 ALab trash，再修改 SQLite row 或写 lifecycle audit event。
- `exp checkout remove` 现在对 inspection checkout directory 使用同一套 trash staging 路径。
- Actual remove 会记录 sanitized trash metadata、token revocation target、submit-capable worktree 的 dirty state，以及 registered filesystem path 是否已经缺失。
- 如果 filesystem move 后 SQLite transaction 失败，ALab 会 best-effort 把 staged path 恢复到原位置；恢复失败时返回 `STORAGE_ERROR`。
- DB/audit 成功后，ALab 会立即删除 staged trash。如果立即删除失败，会写入 active `cache_entries.cache_kind = 'trash'` row，后续由 `cache prune --trash --older-than <days>` 或 `cache prune --trash-all` 清理。
- `cache prune --trash-all` 和 top-level `--all` 现在可以删除 active trash cache row，包括 home trash path 和 sanitized same-parent fallback label。
- 新增 smoke coverage，覆盖 trash cache pruning、worktree remove dry-run/actual trash metadata、token/path state updates，以及 inspection checkout missing-path reconciliation。

仍未完成：

- Whole-project、whole-experiment、validation、run、artifact、log 和 annotation lifecycle completion 已在后续 progress entry 覆盖。
- Standalone artifact/log remove 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest`

## 2026-05-18 Experiment Remove Cascade Trash Staging

已实现：

- `exp remove --cascade` 现在会在 actual deletion 前检查 active experiment locks，并在 dry-run output 中报告稳定 blocker。
- Whole-experiment remove 现在会在 DB/audit mutation 前，把 registered submit worktree、inspection checkout、未被其他对象引用的 experiment log file 和未被其他对象引用的 experiment artifact blob stage 到 ALab trash。
- 如果 staging 后 DB/audit mutation 失败，ALab 会按反向顺序 best-effort 恢复每个 staged path；恢复失败时返回 `STORAGE_ERROR`。
- Experiment token rows 现在会 revoke 并保留用于 audit，不再 hard-delete。Experiment path registry rows 会标记为 `removed`，保留 removed path 可复用语义。
- Audit metadata 会记录 sanitized filesystem target count、absent count、trash mode/label、object kind、object id 和 original path hash，不包含 raw token 或 file content。
- Experiment branch ref deletion 已在后续 progress entry 覆盖。
- Immediate trash deletion 失败时，会复用 worktree/checkout remove 的 pending trash cache-row 清理路径。
- 新增 smoke coverage，覆盖 worktree、inspection checkout、stdout/stderr log file 和 artifact blob 的 experiment remove cascade staging。

仍未完成：

- Annotation standalone remove revision-count audit 已在后续 progress entry 覆盖；standalone artifact/log remove 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths`

## 2026-05-18 Project Remove Whole-Tree Trash Staging

已实现：

- `project remove --cascade` 现在会检查 active project locks，并在 actual deletion 前输出稳定 dry-run blocker。
- Whole-project remove 现在会在 DB/audit mutation 前，把 project root、project control path，以及 active registered experiment/inspection path stage 到 ALab trash。
- Project remove 会对嵌套 filesystem target 去重，已被 project root 覆盖的路径不会重复 stage。
- 如果 staging 后 DB/audit mutation 失败，ALab 会按反向顺序 best-effort 恢复每个 staged path；恢复失败时返回 `STORAGE_ERROR`。
- Project admin credential 和 experiment/inspection token row 会 revoke 并保留用于 audit。Project path registry row 会标记为 `removed`，保留 removed-path reuse 语义。
- Audit metadata 会记录 sanitized filesystem target count、absent count、trash mode/label、target kind/object id 和 original path hash，不包含 raw filesystem path、token value 或 file content。
- 新增 smoke coverage，覆盖 project root、control path、experiment worktree、inspection checkout 的 project whole-tree cascade staging，retained credential/path rows，dependent DB record deletion，以及 pending trash cleanup。

仍未完成：

- Annotation standalone remove revision-count audit 已在后续 progress entry 覆盖；standalone artifact/log remove 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Run Output Summary Hardening

已实现：

- `_run_experiment` 现在返回结构化 execution summary，而不是 positional tuple。
- 顶层 `alab run` output 现在会渲染真实的 created-commit boolean、stdout/stderr preview、captured artifact count，以及 stored run execution 中的 runner warning code。
- `alab run` output 现在与可观察的 run record 在 artifact count 和 runner warning 上保持一致，例如 `ENV_MODE_FULL_UNREDACTED_HOST_ENV`。
- 扩展 local run/observe workflow 的 smoke coverage，断言顶层 run artifact count、多行 stdout preview rendering，以及 warning-code 与 `runs list` 一致。

仍未完成：

- Mutable-scope run enforcement 已由下一条 progress entry 覆盖。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`

## 2026-05-18 Mutable Scope Run Enforcement

已实现：

- `exp create` 现在会记录 repeated `--mutable-include` 和 `--mutable-exclude` 传入的 experiment mutable override。
- `alab run` 现在会在 staging 前验证 worktree 位于注册的 experiment branch，并拒绝 in-progress Git operation state。
- `alab run` 现在会把 dirty staged/unstaged/untracked changes 以及 baseline-to-HEAD full diff 与 bound project mutable policy 和 experiment override 的交集进行校验。
- `.alab/**` context/token 文件会在 mutable dirty checks 中忽略，并且仍然不会被 stage 到 runner commit。
- Out-of-scope change 会在 runner execution 前以 `SCOPE_VIOLATION` 失败，并保留调用方的 worktree changes。
- Mutable path collection 现在启用 Git rename/copy detection，并在 Git 报告 `R*` 或 `C*` status entry 时同时校验 source path 和 destination path。
- 如果 manual commit 的 baseline-to-HEAD full diff 违反 mutable scope，现在会保存一条 `runs.status = error` 记录，其中包含 `mutable_scope.error_code = SCOPE_VIOLATION`、violation paths，且不会执行 runner，同时保持 HEAD 和 worktree 不变。
- 扩展 smoke coverage，覆盖 experiment mutable override narrowing：阻止 dirty `README.md` 变更并保留 worktree 内容，允许 `src/**` 变更创建 ALab run commit 并通过，rename/copy edge cases 会拒绝 out-of-scope paths，并将越界 manual commit 保存为 run error record。
- 新增 invalid Git state smoke coverage，覆盖 detached HEAD、在非 registered branch 上运行，以及 in-progress merge marker。

仍未完成：

- 剩余 runner hardening 应重点转向超出本地 fake-adapter suites 的真实 Docker/Harbor/SkyDiscover 环境。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_run_rejects_invalid_git_states -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`

## 2026-05-18 Observe List Sort Whitelists

已实现：

- 为 list-style observe rows 新增共享 `--sort <field>:<asc|desc>` parser，使用 command-specific field whitelist，并对 unknown field 或非法 direction 返回稳定的 `CONFIG_INVALID`。
- `runs list` 现在支持按 `started`、`ended`、`reward`、`status`、`config-version` 和 `exit-code` 排序。
- `artifacts list` 现在支持按 `created`、`path`、`size`、`status` 和 `content-hash` 排序。
- `logs list` 现在支持按 `created`、`stream`、`size`、`stored-bytes`、`hidden` 和 `truncated` 排序。
- `annotations list` 现在支持按 `created`、`updated`、`target-type`、`target-id`、`status` 和 `created-by` 排序。
- `exp best` 现在会用 `CONFIG_INVALID` 拒绝用户传入的 `--sort`，因为 best ranking 固定使用 reward-policy identity。
- 同步更新 observe collaboration specs、README 状态，以及本地 agent/core 指南。

仍未完成：

- Public Git credential-helper warning fidelity 已由后续 public source-git warning 里程碑覆盖。
- Annotation path/line target validation 已由后续 annotation target validation 里程碑覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Docker Platform Native Fallback Coverage

已实现：

- 固化 Docker 在 Buildx platform reporting 不可用时针对 `linux/amd64` 和 `linux/arm64` 的 per-architecture capability 行为。
- Docker capability probing 已经会从 Docker info 的 native Linux architecture 推导 supported platform；新增 coverage 验证 `aarch64` 会规范化为 `linux/arm64`。
- 同一 coverage 验证当 Buildx 没有报告非 native platform 时，非 native configured platform 仍保持 `unsupported`。
- 这关闭了顶层 Docker platform specificity 缺口；后续 Docker 工作应转向超出本地 fake-Docker contract suite 的真实环境 hardening。

仍未完成：

- 后续 hardening entries 会继续收敛 mutable-scope 和 acceptance coverage 缺口。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_runner_docker.py -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Annotation Path And Line Target Validation

已实现：

- `annotate add --target path:...` 现在会在存储 annotation 前验证 normalized repo path 在 resolved commit 中存在，且是 Git blob 或 tree。
- `annotate add --target lines:...` 现在会验证 normalized repo path 在 resolved commit 中存在，且是 Git blob。
- Line annotation 现在会拒绝 end line 超出 resolved commit 中 captured file contents 的 inclusive range。
- Current-experiment shorthand 仍要求 clean worktree 并存储 concrete HEAD commit，但现在也会根据 project repository 校验 target path。
- 扩展 smoke coverage，覆盖成功的 path/line annotation、missing path rejection、missing line-target rejection 和 out-of-range line rejection。
- 同步更新 observe collaboration specs、README 状态，以及本地 agent/core 指南。

仍未完成：

- Public Git credential-helper warning fidelity 已由后续 public source-git warning 里程碑覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Public Source Git Credential Warning

已实现：

- `--source-git` clone 和 checkout 现在通过 `GIT_TERMINAL_PROMPT=0` 禁用 Git terminal prompts，并通过 `GCM_INTERACTIVE=never` 禁用 Git Credential Manager interactive prompts。
- Public no-key inline `exp create --source-git` 现在会检测已配置的 local Git credential helper，并在 helper 可用时渲染 `PUBLIC_GIT_CREDENTIAL_HELPER_USED`。
- 同一个 warning 会存入 imported source origin metadata，使 dedupe 或后续 source inspection 保留 public import 触发 warning 的原因。
- `exp create` result block 现在包含 repeated `warning` fields 来展示 inline source import warnings；空 warning list 仍由 renderer 省略。
- 扩展 smoke coverage：使用隔离的 Git global config 配置 `credential.helper=store`，验证 public source-git warning output 和持久化 origin metadata。
- 同步更新 CLI docs、README 状态，以及本地 agent/core 指南。

仍未完成：

- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_public_exp_create_inline_source_import -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`
- `git diff --check`

## 2026-05-18 Run Remove Cascade Trash Staging

已实现：

- `runs remove` 现在会阻塞带 dependent artifact 或 log row 的 archived run，除非显式传入 `--cascade`。
- `runs remove --cascade` 现在会阻塞 active dependent artifact/log row，并在同一个 audited operation 中删除已 archived 的 dependent artifact/log row 和 run row。
- Dependent captured artifact blob 和 log file 会在 DB mutation 前走 reference-counted trash staging；共享文件保留原位，未共享文件通过 ALab trash staged。
- 删除 latest run 会从剩余 run 重算 experiment latest run/commit；删除 final run 会保留 closed submission，并设置 `final_run_removed_at`、`final_run_removed_by` 和 `final_run_removed_audit_id`。
- Dry-run 和 actual output 现在会报告 deleted artifact/log count、active dependent count、latest before/after、final-run removal、filesystem target count、planned trash move，以及 pending trash cleanup。
- Audit metadata 会记录 dependent count、active dependent count、latest before/after、final-run removal、sanitized trash label、target object id、absent count 和 path hash，不记录 raw filesystem path。
- 新增 smoke coverage，覆盖非 cascade blocker、active-child cascade blocker、cascade dry-run、final-run removal metadata、dependent row deletion、submission retention、latest recomputation/retention，以及 artifact/log file trash cleanup。

仍未完成：

- Annotation standalone remove revision-count audit 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Validation Remove Reference-Counted Trash

已实现：

- `project validation remove` 现在会阻塞 dependent artifact/log row，除非显式传入 `--cascade`。
- `project validation remove --cascade` 会阻塞 active dependent artifact/log row，并在同一个 audited operation 中删除已 archived 的 dependent row 和 validation row。
- Dependent captured artifact blob 和 log file 会在 DB mutation 前走 reference-counted trash staging；共享 validation/run blob 保留原位，未共享文件通过 ALab trash staged。
- Dry-run 和 actual output 现在会报告 deleted artifact/log count、active dependent count、filesystem target count、planned trash move，以及 pending trash cleanup。
- Audit metadata 会记录 dependent count、active dependent count、sanitized trash label、target object id、absent count 和 path hash，不记录 raw filesystem path。
- 扩展 smoke coverage，覆盖非 cascade blocker、active-child cascade blocker、shared artifact retention、log file trash cleanup、dependent row deletion，以及 validation audit metadata。

仍未完成：

- Annotation standalone remove revision-count audit 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Docker Unavailable And Real Runner Entry

已实现：

- 新增 CLI-level coverage，覆盖 Docker unavailable baseline 行为：Docker-backed `project init` 会保存为 validation `error` record、project status 保持 `invalid` 并 exit `1`，而不是暴露 internal error 或写出 valid project。
- Docker unavailable test 会验证 validation row、record failure reason、stderr log stream，以及没有 active valid config version。
- 新增 opt-in `real_docker` pytest marker 和 `tests/test_real_docker.py` entrypoint。默认会 skip，只有设置 `ALAB_RUN_REAL_DOCKER=1` 时才运行。
- 当 Docker 和所需 image 可用时，真实 Docker test 会用 Alpine container 验证 Docker runner 的实际 `/app`、`/logs/alab` mount、container-visible ALab env、no-network mode 和 stdout reward parsing。
- README 和 test spec 现在记录 opt-in real Docker command。

仍未完成：

- Real Harbor 和 SkyDiscover Docker environment validation 还需要对应 opt-in coverage。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_runner_docker.py`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_real_docker.py`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`

## 2026-05-18 Annotation Remove Revision Audit

已实现：

- `annotate remove` dry-run 现在会报告将删除的 annotation revision 数量，并明确报告零 filesystem target。
- Actual annotation remove 会写入包含 `deleted_revision_count`、零 filesystem target、零 absent path 和空 trash list 的 audit metadata。
- Actual annotation remove 现在会输出 deleted revision count、零 deleted filesystem paths，以及 `trash cleanup pending: false`。
- 扩展 smoke coverage，覆盖 worktree token regeneration 后删除 private annotation，并验证 revision deletion、annotation row deletion、output fields 和 audit metadata。

仍未完成：

- Observe list filter/sort surface 已由后续 observe sort whitelist 里程碑覆盖。
- Public Git credential-helper warning fidelity 已由后续 public source-git warning 里程碑覆盖。
- Annotation path/line target validation 已由后续 annotation target validation 里程碑覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Best Incomparable Warning

已实现：

- `exp best` 和 `observe experiments best` 现在会聚合那些因 bound reward policy identity 与当前 comparable reward policy identity 不同而被排除的 runs。
- 当 incompatible runs 被排除时，`best` 会渲染一个 `object: warning` block，包含 `warning code: BEST_INCOMPARABLE_RUNS_EXCLUDED`、稳定 warning reason 和 `excluded count`。
- 显式 `--config-version` best ranking 不受影响，因为它只比较该 config version。
- 扩展 smoke coverage：两个 run 完成后改变 project reward direction，添加一个新的 compatible run，并验证两个旧 incompatible run 的 warning count。

仍未完成：

- Observe list filter/sort surface 已由后续 observe sort whitelist 里程碑覆盖。
- Public Git credential-helper warning fidelity 已由后续 public source-git warning 里程碑覆盖。
- Annotation path/line target validation 已由后续 annotation target validation 里程碑覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Context Self-Repair Git Checks

已实现：

- Self-token `context repair --path <dir>` 现在会验证 target path 是 Git worktree，且 common Git directory 是该 ALab project repository。
- Worktree self-repair 现在要求 target checkout 位于 experiment 注册的 `experiments.branch_name`。
- Inspection self-repair 现在要求 target checkout HEAD commit 匹配 marker 中的 pinned inspection commit。
- 既有 self-token safety gates 保持不变：old registered realpath 必须不存在，marker `token_id` 必须匹配已验证的 token credential，且 target realpath 不能已经被注册。
- 新增 smoke coverage：用 `git worktree move` 移动 experiment worktree，验证 detached-HEAD self-repair 被拒绝，再切回 registered branch 后 repair 成功。

仍未完成：

- Observe list filter/sort surface 已由后续 observe sort whitelist 里程碑覆盖。
- Public Git credential-helper warning fidelity 已由后续 public source-git warning 里程碑覆盖。
- Annotation path/line target validation 已由后续 annotation target validation 里程碑覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Experiment Branch Ref Deletion

已实现：

- `exp remove --cascade` 现在会在 dry-run 阶段解析并输出 canonical experiment branch ref。
- Actual experiment remove 会在 filesystem staging 后、DB/audit mutation 前删除 experiment branch ref。
- 如果 branch deletion 成功但后续 DB/audit mutation 失败，ALab 会在恢复 staged filesystem paths 前，best-effort 把 branch ref 恢复到原 commit。
- Experiment remove audit metadata 现在会记录 branch ref、previous branch commit、该 ref 是否已删除，以及该 ref 是否已经缺失。
- 新增 smoke coverage，验证 experiment branch ref 在 remove 前存在、remove 后缺失，并出现在 command output 和 audit metadata 中。

仍未完成：

- Annotation standalone remove revision-count audit 已在后续 progress entry 覆盖；standalone artifact/log remove 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Artifact 和 Log Reference-Counted Trash

已实现：

- Standalone `artifacts remove` 和 `logs remove` 现在会在 DB/audit mutation 前计算 filesystem targets。
- Captured artifact blob 只有在没有任何剩余 artifact row 引用同一 blob path 时才会 stage 到 ALab trash。
- Log file 只有在没有任何剩余 log row 引用同一 file path 时才会 stage 到 ALab trash。
- Dry-run output 会报告 `deleted filesystem paths`、受影响 filesystem path 和 planned trash move。
- Actual remove 会记录 sanitized trash metadata；如果 immediate deletion 失败，会报告 pending trash cleanup。
- 新增 smoke coverage，覆盖两个 run 共享 artifact blob 的引用计数删除，以及 standalone log file remove。

仍未完成：

- Annotation standalone remove revision-count audit 已在后续 progress entry 覆盖。
- Cross-device same-parent fallback 已在 staging helper 中实现，但还没有 filesystem-level integration test 覆盖。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash -q`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-18 Observe Contract Hardening

已实现：

- `exp search` 现在应用与 experiment list/best 相同的 `--reward-min` 和 `--reward-max` filter。
- Experiment `--sort reward:asc` 现在会把没有 parsed reward value 的 experiment 排在 concrete reward value 之后，匹配文档中的 null-last sort rule。
- Experiment search 现在只会把 caller 可见的 latest annotation body 纳入搜索语料，因此 private annotation 不会影响 peer-token search result。
- Token-only log observe command 现在会立即以 `SCOPE_VIOLATION` 拒绝 `--include-hidden`，即使当前选择的 visible row 不是 hidden log。
- Artifact 和 log export 现在要求 parent directory 已存在，不再创建缺失的 parent directory。
- 扩展 smoke coverage，覆盖 reward-filtered search、reward null-last sorting、private annotation search visibility、token hidden-log option rejection，以及 missing export parent。

仍未完成：

- Remaining hardening 应聚焦真实 Docker/Harbor/SkyDiscover 环境，而不是本地 fake-adapter suite。
- 更深入的 Docker platform specificity 仍待实现。

验证：

- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m compileall -q src tests`
- `PYTHONPATH=src /opt/homebrew/Caskroom/miniconda/base/bin/python3 -m pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPATH=src uv run pytest -q`
- `UV_CACHE_DIR=/Users/hobeter/Desktop/code/ALab/.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check`

## 2026-05-19 Capability Surface Hardening

已实现：

- 将 CLI help/preflight 的粗粒度 availability check 替换为 context-sensitive command surfaces，分别覆盖 global、project-public、experiment-token、inspection-token、explicit-admin 和 explicit-root caller。
- Public project context 现在只暴露 safe status，以及 active valid project config 允许时的 public experiment creation。
- Experiment token context 现在暴露 run/submit、visible observe/read/export surfaces、token-owned lifecycle archive/unarchive operations、tags、annotations 和 self inspection checkout creation，但不暴露 project/source/config/key/cache/audit maintenance commands。
- Inspection token context 现在只暴露 status、只读 observe/export surfaces 和 matching inspection checkout removal；run、submit、tags、annotations、run/archive lifecycle 等 mutation commands 会在 capability preflight 阶段被阻止。
- Ambient `ALAB_KEY` 不再扩大 help 或 public/token command surfaces。Root/admin command 需要显式 `--key` 或 `--key-stdin` 才会在 preflight 阶段可用。
- 新增 smoke coverage，覆盖 project、experiment、inspection、explicit-admin 和 ambient-key help/preflight behavior。

仍未完成：

- `docs/spec_tests.md` 中更完整的 golden CLI matrix 仍需要按命令系统覆盖 field order、aliases、errors 和 nested help。
- Remaining runner hardening 仍应聚焦真实 Docker/Harbor/SkyDiscover 环境，而不是本地 fake-adapter suite。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`

## 2026-05-19 CLI Contract And Context Path Hardening

已实现：

- 收紧 global option pre-scan，`--key-stdin` 后面再次出现 `--key` 现在会以 `CONFIG_INVALID` 失败，符合双向 conflict contract。
- 新增 CLI contract smoke coverage，覆盖 `--key-stdin` conflict 和 standalone `--` 停止解析 global option 的行为。
- 更新 inspection checkout authorization，experiment token 现在可以为任何 token-visible experiment 创建 inspection checkout，不再只能 checkout 自己的 experiment。
- 为 experiment worktree creation、worktree restore 和 inspection checkout creation 添加 shared context path validation。
- 新 context path 现在必须缺失或为空，不能复用 active registered path；只允许嵌套在 same-project marker-only project control context 下，不能创建在 experiment 或 inspection context 内部。
- 收紧 `project secret gc`，要求 `--dry-run` 和 `--apply` 必须二选一，避免两个 flag 同时出现时被当作 apply 执行。
- 扩展 smoke coverage，覆盖 visible peer inspection checkout、从 experiment context 默认创建 nested experiment 被拒，以及 strict secret-GC selector handling。

仍未完成：

- Stale `running` run/validation interruption semantics 和完整 golden CLI matrix 仍需要更广覆盖。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path -q`

## 2026-05-19 Stale Running Record Interruption

已实现：

- 添加 shared stale-record interruption helper，用于处理 ALab 进程中断后遗留的 `runs.status = 'running'` 和 `project_validations.status = 'running'` rows。
- 后续 status、run、submit、project validation、validation lifecycle，以及 run lifecycle archive/remove 路径现在会先把匹配的 stale running rows 标记为 `interrupted`，然后再继续执行。
- Interrupted run 和 validation records 会保留原 row id，并写入 sanitized record metadata，其中包含 `interrupted = true` 和 stable failure reason。
- Interrupted validation 还会把对应 running `project_config_versions.validation_status` 更新为 `interrupted`。
- 当 interrupted validation 属于 latest attempted project config 时，project 会变为 `invalid`，并清空 active validation/config pointers，匹配 skipped/interrupted baseline 不能证明项目可运行的规则。
- 新增 smoke coverage：手动注入 stale running run 和 validation rows，执行 `status`，并验证 run、validation、config 与 project state reconciliation。

仍未完成：

- Stale interruption 已有 service/CLI 层覆盖；lock ownership 与 heartbeat replacement semantics 仍需要围绕真实并发操作补更深入测试。
- 完整 golden CLI matrix 仍比当前 smoke coverage 更广。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`

## 2026-05-19 Nested Help And Secret Input Contract

已实现：

- 收紧 top-level help parsing，`alab help` 和 `alab --help` 现在只接受文档约定的 `--all` 与 `--explain` options；未知或重复 help options 会以 `CONFIG_INVALID` 失败。
- 为 nested `--help` requests 添加 command-level help selection。被选择命令的 non-help arguments 会传入与 execution preflight 相同的 capability resolver，因此 `exp create --project <id> --help` 等 project-specific public availability 会与直接调用保持一致。
- Nested command help 现在只渲染被选择的 command row；当命令存在但当前 context 不可用时，会渲染 locked row，并且不会进入 handler 或读取 value/body files。
- 新增 smoke coverage，验证 `--output rich` 是单次 command renderer selection，不会持久修改 global config。
- 新增 smoke coverage，验证 `project secret set --value-stdin` 与 `--value-file` 会拒绝 empty values、embedded newlines、NUL bytes、短于四个 UTF-8 bytes 的值，以及只剥离一个 trailing newline 后仍包含换行的 double trailing newlines。
- 新增 preflight 覆盖，验证不可用的 project secret mutation 会在读取缺失 `--value-file` 前以 `COMMAND_UNAVAILABLE` 失败。

仍未完成：

- `docs/spec_tests.md` 中 command-by-command golden output matrix 仍需要更广的 field-order、alias 和 error text 覆盖。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_project_secret_input_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source Origin Duplicate-Option Hardening

已实现：

- 收紧 shared source-origin parsing，使重复 `--source-path`、`--source-git`、`--source-empty` 与 `--source-ref` 以 `CONFIG_INVALID` 和明确 duplicate-option message 失败，而不是落入泛化 source-origin conflict。
- 保持真正 multiple source origins 以及 `--source-subdir` 缺少 path/Git source 等 source selector scope conflicts 的既有 `SOURCE_INVALID` 行为。
- 增加 smoke coverage，覆盖 `project init` 与 `source import` 中重复 local source origin、重复 `--source-empty`，以及 `exp create` 中重复 `--source-ref`，同时保留 no-write failure assertions。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 From-Experiment Duplicate-Option Hardening

已实现：

- 收紧 `exp create --from-exp`，使重复 `--from-exp` 以 `CONFIG_INVALID` 和明确 duplicate-option message 失败，而不是落入泛化 source-origin conflict。
- 保持 `--from-exp` 与 explicit source selectors 组合时的既有 source-origin conflict 行为，并保留 `--from-commit` duplicate validation。
- 更新 from-experiment smoke coverage，验证重复 `--from-exp` 不会创建 child experiment row、worktree 或 add audit。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Exact-One Pair Duplicate-Option Hardening

已实现：

- 收紧 shared exact-one option-pair validator，使重复选项会先以明确的 `CONFIG_INVALID` duplicate-option message 失败，再进入更宽泛的 “requires exactly one of” 关系检查。
- 将一致的 duplicate-priority 行为应用到 backup pruning、project secret value input、project secret GC、submit summary/feedback input、inspection checkout removal selectors 与 annotation body input。
- 更新 smoke coverage，保持既有 missing/conflicting-pair errors，同时验证 duplicate-specific failures 仍会在 file reads、mutation writes、token/path revocation 与 annotation revision writes 前发生。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Force/Confirm Duplicate-Option Hardening

已实现：

- 收紧 shared force-confirm guard，使重复 `--force` 与 `--confirm` 会先以明确的 `CONFIG_INVALID` duplicate-option messages 失败，再进入更宽泛的 confirmation mismatch check。
- 保持 destructive remove/catalog operations 在缺少 `--force`、缺少 `--confirm` 和 confirmation value 错误时的 command-specific confirmation messages。
- 更新 shared smoke helper coverage，使所有 destructive confirmation guard call sites 现在都会断言 duplicate-specific failures，同时保留周边测试已有的 no-mutation checks。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Admin Annotation Private Target Hardening

已实现：

- 收紧 annotation privacy selection，使 root/admin caller 不能单独使用 `--private` 并意外创建 project-visible annotation。
- Root/admin private annotations 现在必须使用 `--private-to-exp <exp_id>`；experiment token caller 保持既有 `--private` 行为，并绑定到自身 experiment identity。
- 增加 collaboration smoke coverage，验证 project-context admin `annotate add --private` 会在写入 annotation 或 revision rows 前以 `CONFIG_INVALID` 失败。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Public Invalid Status Hardening

已实现：

- 收紧 invalid projects 的 no-key public `status --project <id>`，使其不再渲染 task text 或其他 project summary content。
- Invalid public status 现在只渲染安全的 public context block，包含 project id、invalid status，以及文档约定的 admin/root validation next action。
- 增加 smoke coverage，验证 invalid public status 会省略 task/project text，同时保留既有 valid public status shape。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source Show Selector Conflict Hardening

已实现：

- 收紧 `source show`，使 positional source selector 与 `--source-ref` 不能同时提供。
- 保持合法 source id/ref lookup behavior 不变，同时确保 ambiguous dual selectors 会在 source lookup 前以 `CONFIG_INVALID` 失败。
- 增加 smoke coverage，验证冲突 `source show <selector> --source-ref <ref>` inputs 会渲染稳定 error block。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Experiment Observe Filter And Sort Matrix Closure

已实现：

- 扩展 `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`。
- 该测试现在固定 experiment created/updated timestamps，并直接覆盖 `created`、`updated`、`name` 和 `status` sort fields。
- 增加 open、closed 和 archived experiments 的 status filter coverage，包括 archived inclusion。
- 通过专门的 two-tag experiment 增加 repeated `--tag` AND coverage。
- 增加一个 distinct inline source experiment，使 `--source-id` filtering 证明跨多个 source ids 的排除，而不只是匹配 default source。
- 增加 source、tag、name、status 和 name-sort filters 的 focused search-path coverage，使用同一 experiment row helper。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 experiment list/search/best filter、pagination 和 sort matrices 不再是 active work。剩余 active evidence 是 grouped audit-row decomposition 加 release gates。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`

## 2026-05-21 Observe List Filter And Sort Matrix Closure

已实现：

- 扩展 `tests/test_smoke.py::test_observe_list_pagination_contracts`。
- 该测试现在覆盖 run filters：experiment、status、config version、commit prefix、reward range、runner type、exit code、failure reason、started/ended ranges、archive inclusion，以及包括 reward null-last ordering 在内的 sort fields。
- 同一测试覆盖 artifact filters：experiment、run、validation、root、status、path query、content hash、created range、size range、archive inclusion，以及 artifact sort whitelists。
- 同一测试覆盖 log filters：experiment、run、validation、stream、truncated、created range、archive inclusion，以及 log sort whitelists。
- 同一测试覆盖 annotation filters：target type、target id、target alias、author、created-by、private、query、created/updated ranges、archive inclusion，以及 annotation sort whitelists。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 run/artifact/log/annotation list filter/sort matrices 不再是 active work。剩余 observe evidence 是 experiment list/search filter/sort row mapping。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_observe_list_pagination_contracts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_observe_list_pagination_contracts tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-20 Experiment Query Duplicate-Option Hardening

已实现：

- 为 `exp list`、`exp search` 与 `exp best` 添加 shared experiment query duplicate-option guard，覆盖 filters、reward bounds、pagination 与支持的 sorting。
- 将 `exp list` project resolution 切换为其他 observe commands 使用的同一 project-id helper，因此重复 `--project` 现在会以 `CONFIG_INVALID` 失败。
- 保留重复 `--tag` 的 AND 语义，同时增加覆盖 experiment list/search/best 中重复 `--project`、time filter、reward bound 与 pagination options 的 smoke coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`

## 2026-05-21 Annotation Target Resolution Coverage

已实现：

- 新增 `tests/test_smoke.py::test_annotation_path_targets_resolve_commits_and_reject_dirty_shorthand`。
- 该测试证明 experiment、run、artifact annotation object targets，以及使用 `HEAD`、`head`、`latest`、`final`、`best` 和 unambiguous commit SHA prefix 的 explicit path targets。
- 它验证 resolved commits 和 stored `target_json` 使用 concrete commit SHAs，而不是 moving aliases。
- 它证明 path targets 可以指向 Git trees、line targets 必须指向 blobs、invalid line ranges 与 normalized repo-path failures 会拒绝且不创建 annotations，并且 current-worktree shorthand 会拒绝 staged、unstaged、deleted、renamed、copied 和 untracked changes。
- 更新 completion audit 和 progress dashboard，将 annotation target resolution 标为 default CLI/storage surfaces 下已证明。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_annotation_path_targets_resolve_commits_and_reject_dirty_shorthand -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` 未发现匹配。
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` 未发现匹配。

## 2026-05-21 Log And Artifact Access Coverage

已实现：

- 扩展 `tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation`，使 `logs show` 证明 byte-limited stored log content 来自与 `logs export` 相同的 truncated/redacted bytes。
- 扩展 `tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs`，使 token contexts 直接拒绝 `logs show --include-hidden`，并断言 Harbor hidden-log backing files 没有 artifact rows。
- 扩展 SkyDiscover Python 和 Docker smoke tests，断言 hidden evaluator log backing files 没有 artifact rows。
- 更新 completion audit 和 progress dashboard，将 default local log access、artifact export，以及 adapter hidden-output non-artifact behavior 标为已证明。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` 未发现匹配。
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `git diff --cached --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_log.md docs/progress_log_cn.md` 未发现匹配。
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Observe List Filter Duplicate-Option Hardening

已实现：

- 收紧 `runs list`、`artifacts list` 与 `logs list` duplicate-option validation，在 command entry 覆盖全部已文档化 filter options。
- 关闭 `runs list` 重复 `--project` 缺口，使重复 project selectors 以 `CONFIG_INVALID` 失败，而不是静默使用第一个值。
- 增加 duplicate run-list `--project`、artifact-list `--run` 与 log-list `--truncated` inputs 的 smoke coverage，并与既有 duplicate sort/pagination coverage 配套。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Observe List Duplicate Sort/Pagination Hardening

已实现：

- 收紧 `runs list`、`artifacts list` 与 `logs list` duplicate-option validation，使 `--sort`、`--limit` 与 `--offset` 在 command entry 被拒绝，而不是等 observe queries 运行后才失败。
- 保持合法 observe sorting 与 pagination behavior 不变，同时让 run、artifact、log 与 annotation list surfaces 的 duplicate sort/pagination errors 保持一致。
- 增加 duplicate log 与 artifact list `--limit`/`--sort` attempts 的 smoke coverage，并沿用既有 run list duplicate coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation List Duplicate Sort/Pagination Hardening

已实现：

- 收紧 `annotations list` duplicate-option validation，在 command entry 覆盖 time filters、`--sort`、`--limit` 与 `--offset`。
- 保持合法 annotation list sorting 与 pagination 不变，同时确保重复 sort/pagination options 会在 annotation queries 与 revision filtering 前以 `CONFIG_INVALID` 失败。
- 增加 smoke coverage，验证重复 `--limit` 与重复 `--sort` attempts 会渲染稳定 error blocks。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation List Target Selector Hardening

已实现：

- 收紧 `annotations list` target filtering，使 `--target-id` 与兼容性的 `--target` selector 不能同时提供。
- 保持合法 annotation list filters 不变，同时确保 ambiguous target selector input 会在任何 annotation query 运行前以 `CONFIG_INVALID` 失败。
- 增加 smoke coverage，验证冲突 annotation target selectors 会渲染稳定 error block。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Audit List Duplicate-Option Hardening

已实现：

- 收紧 `audit list` duplicate-option validation，使其覆盖每一个已接受的 filter 与 pagination option，包括 `--actor`、`--created-after`、`--created-before`、`--limit` 与 `--offset`。
- 保持合法 filters 的 audit query behavior 不变，同时确保重复 actor/time/pagination options 会以 `CONFIG_INVALID` 失败，而不是静默使用第一个值。
- 增加 smoke coverage，验证重复 `--actor` 与重复 `--limit` attempts 会渲染稳定 error blocks。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Audit List No-Positional Argument Hardening

已实现：

- 收紧 `audit list`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 audit authorization 与 duplicate-filter validation priority，同时确保 extra positional arguments 会在 audit event queries 前被拒绝。
- 增加 smoke coverage，验证 `audit list` 会在合法 `--object-type` 与 `--object-id` filters 旁拒绝 extra positional arguments。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation Add/List No-Positional Argument Hardening

已实现：

- 收紧 `annotate add` 与 `annotations list`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 扩展 shared positional parser，使其识别 annotation list filter values（`--target-type`、`--target-id` 与 `--created-by`），同时确保 extra positional arguments 会在 annotation body file reads、annotation row/revision writes 或 annotation list queries 前被拒绝。
- 增加 annotation smoke coverage，验证 extra positional add attempts 会保留 annotation/revision counts 并在 missing body-file reads 前失败，也验证 annotation list 拒绝相同 grammar drift。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Text Limit And Lifecycle Reason Hardening

已实现：

- 将 shared UTF-8 byte-limit validation 扩展到 project config text fields、source display names、experiment names、tag slugs 和 lifecycle remove reasons。
- Project init 和 project config mutation 现在会在持久化 config version 前拒绝 empty 或超过 120 bytes 的 `project.name` / `task.description`。
- Source import display names 和 experiment names 现在会拒绝 empty 或超过 120 bytes 的值。
- Experiment goal text 现在会拒绝超过 65536 bytes 的值。
- Experiment tag creation、tag mutation 和 tag filters 现在使用同一个 shared slug validator；normalized slug 超过 64 bytes 时会拒绝，而不是 silent truncation。
- `exp create` 现在会在 source import 或 Git worktree creation 前校验 goal text、tag slugs、mutable overrides 和 visibility overrides，因此 invalid no-`--path` creates 不会再在 caller cwd 留下 default worktree directories。
- Lifecycle remove reason 现在使用同一个 shared reader，并执行文档约定的 65536-byte limit，因此 invalid reason 会在 dry-run rendering、destructive filesystem staging、trash finalization、DB mutation 或 audit writes 前被拒绝。
- SkyDiscover catalog remove 现在会在删除 registered catalog path 前校验过长 reason。
- 新增 deterministic filesystem coverage，通过模拟 home-trash rename 发生 `EXDEV`，验证 cross-device trash staging fallback 会使用 same-parent `.alab-trash-<audit_id>` staging、清理未使用的 home trash directory，并可恢复原路径。
- 新增 exact-boundary acceptance fixtures，覆盖 120-byte 多字节 display names、65536-byte 多字节 project task/goal values、65536-byte submit summary/feedback file inputs、65536-byte annotation body file input、300-byte run/submit messages，以及 64-byte tag slugs。
- 扩展 smoke coverage，覆盖 project/source/experiment display-name limits、多字节 project/source/experiment display-name byte limits、多字节 project task/goal byte limits、experiment goal limits、tag limit rejection、failed `exp create` worktree cleanliness、多字节 run/submit message byte limits、多字节 submit summary/feedback byte limits、file-input submit summary/feedback byte limits、多字节 annotation-body byte limits、file-input annotation-body byte limits、lifecycle dry-run reason preflight、多字节 lifecycle reason byte limits、long catalog-remove reason preflight，以及 reason validation 失败后 catalog state 保持不变。

仍未完成：

- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_skydiscover_catalog_lifecycle -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Config And Archive Contract Coverage

已实现：

- 收紧 global `config set`：只能编辑文档列出的 fields；`output.format` 仍只允许 `"text"`；numeric fields 必须是正整数。
- 收紧 global `config reset`：caller 必须传入一个 documented field 或 `--all`，且 field reset 只从 default config 恢复该 field，不会重写无关值。
- `config set output.format "text"` 现在可以修复 parseable config 中被意外改坏的 persisted output format。
- `config validate` 现在会拒绝手工编辑后 numeric fields 非法的 global config，而不是把它渲染为 valid。
- 新增 debug-mode 覆盖，验证 internal exceptions 只有在 `ALAB_DEBUG=1` 时才打印 traceback，普通输出仍保持稳定 ALab error object。
- 扩展 observe lifecycle 覆盖：archived log/artifact show by id 在授权时仍成功，但 export 必须显式传入 `--include-archived`。
- 新增 project config validation 覆盖，验证 `runner.network = "host"`、非法 environment variable names，以及通过 `project config set` 直接修改 `secret_env.*` 都会被拒绝。

仍未完成：

- 完整 command-by-command golden output fixtures 仍比当前 smoke suite 更广。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_stack_trace_only_for_internal_errors tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Audit Filters And Token Selector Disclosure

已实现：

- 将 `help` 加入 registry-backed canonical command row，因此 context-aware help output 现在包含文档约定的 help command 自身。
- 更新 `help --all` rendering，先列出 available command rows，再列出 locked rows，并在每组内部保持 registry order。
- 收紧 `audit list --object-id`：当它与已知 `--object-type` 搭配时，会为 project/source/experiment/worktree/run/artifact/log/annotation/validation/credential/inspection-checkout filters 校验 ALab object-id prefixes，并为 catalog/cache/backup filters 校验稳定 literal。
- 收紧 `audit list --actor`、`--limit` 和 `--offset`，invalid credential ids 与 non-integer pagination 现在会以 `CONFIG_INVALID` 失败，而不是落入 generic errors。
- 收紧 `annotations list --target-id`：当选择 object-backed target types 时，experiment/run/artifact ids 必须是完整 ID。
- 更新 token-scoped observe 与 annotation selectors，使 missing 或 invisible experiments、runs、artifacts、logs 和 annotations 返回不泄露区别的 `SCOPE_VIOLATION` reason，而不是精确 `*_NOT_FOUND` details。
- 扩展 smoke coverage，覆盖 help row/order behavior、audit object-id 与 pagination validation、annotation target-id validation，以及 token not-visible-or-not-found selector behavior。

仍未完成：

- 部分 generic audit object types 仍有意保留 literal 或 legacy object ids，因为历史 audit rows 并不全部使用 ALab object-id prefixes。
- 完整 golden CLI matrix 仍需要 command-by-command field-order 和 alias coverage。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Time Filter And Object Selector Hardening

已实现：

- 收紧 RFC 3339 parsing，time filters 必须使用 `T` 分隔日期与时间，并且必须带 `Z` 或 numeric `+HH:MM`/`-HH:MM` offset。
- 将 `audit list --created-after/--created-before` 改为复用 observe 和 experiment time filters 使用的同一 RFC 3339 normalization path。
- 将完整 ALab object-id validation 接入用户可直接选择的 projects、credentials、validations、sources、experiments、runs、artifacts、logs、annotations、audit events、inspection token selectors，以及 observe list filters。
- Source refs 保持为明确的 source-selector 例外，Git commit selectors 继续与 ALab object-id validation 分离。
- 扩展 smoke coverage，覆盖 strict audit time filters、不完整 credential/source/run/log/artifact/annotation selectors、同一路径上的 valid full-id behavior，以及 config、log、artifact exports 的 `OUTPUT_EXISTS`/`--overwrite` 行为。

仍未完成：

- Audit `--object-id` 仍保持 generic，因为它可能指向多种 object types；等 audit filter matrix 按 command family 覆盖后，可以继续做 object-type-specific validation。
- 更广的 golden CLI matrix 仍需要系统覆盖 field-order 和 command-family error text。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Saved Result Failure And Alias Contract Coverage

已实现：

- Saved run failure 现在会在 normal run payload 后追加稳定 result-failure fields：`error code`、CLI `exit code`、`reason` 和 `next`。
- 通过 `project init`、`project validate` 和 runtime-affecting `project config set` 渲染的 baseline validation failure 现在会追加 `BASELINE_VALIDATION_FAILED` result-failure fields，不再只依赖 inferred exit status。
- Project init 在 initial baseline 非 valid 时现在渲染 validation next action；valid project 仍保留 experiment-create next action。
- 新增 debug-mode 覆盖，证明 saved failed run 在 `ALAB_DEBUG=1` 下不会打印 CLI traceback；只有 internal/system failures 会打印。
- 扩展 alias 覆盖，将 `exp show`、`runs list`、`logs list`、`artifacts list`、`annotations list` 和 `annotations show` 与对应 canonical `observe ...` command paths 进行输出对比，并覆盖 alias 后置 global `--home` placement。
- 新增 Docker-unavailable baseline 覆盖，验证新的 `BASELINE_VALIDATION_FAILED` result fields。

仍未完成：

- 完整 CLI golden matrix 仍需要更广的 command-by-command field-order 和 error text fixtures。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit Result Failure Contract

已实现：

- `submit` 现在会在运行 experiment runner 前校验 summary、feedback 和 refs，因此 invalid submit inputs 不会创建 saved run 副作用。
- Summary 和 feedback 现在必须且只能提供 direct text value 或 file input 之一，符合 V1 CLI contract。
- Submit refs 现在使用 shared repeated-option parser，按 first-seen order 去重，拒绝 missing ref values，保持 `--ref none` 与 experiment refs 互斥，并根据 submitting token 可见 experiment set 校验 experiment refs。
- Submit summaries 和 feedback 现在会在存储任何 submission text 前复用 active-secret body check。
- 缺少 reusable passed run 时，现在返回 `object: submission` result failure，包含 `submit accepted: false`、`RUNNER_FAILED` 和文档约定的 `--rerun` next action，而不是 generic error block。
- `submit --rerun` 的 final-run failure 现在保留 failed run record，但返回 `submit accepted: false`、保持 experiment open、不写 submission row，并追加稳定 result-failure fields，且 debug 模式不打印 traceback。
- 新增 smoke coverage，覆盖 invalid submit input preflight、structured failed-submit output、保留 failed run record、experiment open state，以及 missing reusable-run output。
- 扩展 submit ref preflight coverage，覆盖 trailing `--ref` missing value、`--ref` 后接另一个 option、`--ref none` 与 experiment ref 混用、不可见 experiment refs、完整但缺失的 experiment refs，以及所有 invalid ref cases 后不产生 run side effects。

仍未完成：

- 完整 CLI golden matrix 仍需要更广的 command-by-command fixtures。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit Input Limits And Visibility Override

已实现：

- 新增 shared UTF-8 byte-limit validation，用于 run messages、submit messages、submit summaries、submit feedback 和 annotation bodies。
- `run --message` 和 `submit --message` 现在会在 runner execution 前拒绝超过 300 bytes 的值。
- Submit summary 和 feedback 现在会拒绝超过 65536 bytes 的值，无论是 direct input 还是 file input，并且发生在 runner execution 或 submission storage 之前。
- Submit summary 和 feedback 的 secret-value rejection 现在渲染 field-specific errors，不再复用 annotation-body reason。
- Annotation direct empty body 现在符合文档中的 exactly-one input rule，因为 `--body ""` 会被视为已提供的值，而不是 missing option。
- Experiment creation 现在会遵守 `--visibility-scope` 和 `--visible-exp`，把 project visibility policy 与 requested override 的交集存为 experiment visibility upper bound。
- 新增 invalid visibility override 组合校验：`--visible-exp` 必须搭配 explicit visibility；non-explicit visibility 拒绝 visible-exp ids；explicit visibility 必须至少提供一个 visible experiment id。
- 扩展 smoke coverage，覆盖 submit length limits、submit secret rejection、invisible submit refs、invalid submit input 不产生 run 副作用，以及 narrowed experiment visibility。

仍未完成：

- 完整 CLI golden matrix 仍需要更广的 command-by-command fixtures。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Multiline Text Rendering Contract

已实现：

- 新增 explicit renderer value 用于 multiline user text，让普通 scalar fields 继续保持紧凑，同时 task、goal、status task 和 annotation body fields 遵守文档中的 text-output contract。
- 空的 non-null multiline text 现在会渲染为带 `[empty]` 的 multiline field，与 nullable `none` 和 literal user text `none` 区分。
- Project show、project config show、status、annotation observe/show 现在对 user-authored text fields 使用 explicit multiline rendering。
- 扩展 smoke coverage，覆盖 renderer 层 multiline、empty、nullable 行为，以及 CLI annotation body rendering，包括 `--body ""`。

仍未完成：

- 完整 CLI golden matrix 仍需要更广的 command-by-command fixtures。
- Real Harbor 与 SkyDiscover Docker environment validation 仍是 fake-adapter suite 之外的 opt-in hardening 缺口。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_text_renderer_object_block tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker-Backed Adapter Entry Points

已实现：

- 扩展 opt-in `real_docker` pytest entrypoint，使 `ALAB_RUN_REAL_DOCKER=1` 现在覆盖 Docker runner、Harbor shared verifier execution 和 SkyDiscover Docker evaluator execution。
- 新增真实 Harbor fixture，运行 Alpine verifier container，检查 candidate workspace 与 run directory mounts，写入 `reward.json`，并验证 hidden verifier output capture。
- 新增真实 SkyDiscover Docker fixture，构建 Alpine evaluator image，在 `network = "none"` 下对 mounted candidate workspace 运行 evaluator，解析 JSON metrics，并验证 hidden evaluator stderr capture。
- 所有真实 Docker-backed tests 仍默认 skipped，因此 normal suite 不会意外拉取 images。
- 更新 README 和 README_cn setup guidance，说明更完整的 opt-in Docker-backed coverage。

仍未完成：

- 完整 CLI golden matrix 仍需要更广的 command-by-command fixtures。
- 如果未来 hardening 需要 networked `uv` installs，可单独增加 Real SkyDiscover Python dependency-installation validation 的 opt-in environment test。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 CLI Golden Foundation Coverage

已实现：

- 新增 shared smoke helpers，用于从 strict text object blocks 中提取 rendered field-label order。
- 将 `auth init`、`auth root regenerate`、`config show`、`config set` 和 `config reset` coverage 从宽松 substring checks 收紧为符合 CLI contract 的 ordered field-label checks。
- 新增 root regeneration lifecycle coverage，证明旧 root key id 会作为 revoked key 渲染，并且旧 raw root key 不能继续认证。
- 收紧 nested command help coverage：selected help output 现在校验 `help` block field order 与 `help_command` row field order，并确认 global help 以 registry-backed `help` row 开头。
- 新增 project public `status` 和 `project config show` field-order checks，并覆盖 actual CLI command paths 中的 multiline task/goal output。

仍未完成：

- 完整 CLI golden matrix 仍需要在初始 auth/config/help foundation 之外补充更广的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run Submit And Observe Golden Coverage

已实现：

- 将核心 local agent workflow 中 `exp create`、`run` 和成功 `submit` 输出，从宽松 substring checks 收紧为 ordered field-label checks。
- 新增 submit result-failure 输出的 ordered field-label checks，确保 appended diagnostic fields 在正常 submit summary fields 之后保持稳定。
- 新增 runs、logs、artifacts 的 observe/list row order coverage，包括 hidden-log availability 与 warning-code 的位置。
- 修正 archived log export 周围的 smoke test capture boundary，避免 artifact-list assertions 被前一个命令输出污染。

仍未完成：

- 完整 CLI golden matrix 仍需要在当前 auth/config/help、project status/config、run/submit 和 observe-list coverage 之外继续扩展 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Tag And Maintenance Golden Coverage

已实现：

- 新增 project config mutation/export、secret GC 与 stale-lock clearing 输出的 ordered field-label coverage。
- 新增非默认 source lifecycle 路径上 source import/show/archive/unarchive 输出的 ordered field-label coverage。
- 新增 experiment tag add/list/remove 输出的 ordered field-label coverage。
- 通过测试记录当前 rendered text blocks 的契约：空 list-valued fields 会被省略，非空 tag lists 仍按顺序渲染。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到剩余 lifecycle remove、checkout/repair、audit、search/best surfaces 的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Audit Search And Best Golden Coverage

已实现：

- 新增 shared experiment field-label expectations，覆盖 `exp list`、`exp search`、`exp show` 和 `exp best`/`observe experiments best` output blocks。
- 将 search privacy behavior 固定到 content filtering 与 private annotation text 在当前 context 不可见时的 empty-output rendering。
- 新增 incomparable best-run exclusions 的 warning-block field-order coverage。
- 新增 `audit list` 与 `audit show` 的 ordered field-label coverage，包括 retained sanitized metadata 的位置。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到 lifecycle remove、checkout/repair、token regeneration、artifact/log show/export/archive surfaces 的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Artifact And Log Operation Golden Coverage

已实现：

- 新增 log 与 artifact object blocks 的 shared field-label expectations，使 list/show/export paths 校验同一套 output contract。
- 将 log export、overwrite export、archived show、archive 和 include-archived export coverage 从 object-presence checks 收紧为 ordered field-label checks。
- 将 artifact export、overwrite export、archived show、archive 和 include-archived export coverage 从 object-presence checks 收紧为 ordered field-label checks。
- 新增可复用 archive-result field-label expectations，覆盖 archive status transitions 与 audit id 的位置。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到 lifecycle remove、checkout/repair、token regeneration、unarchive/remove operation surfaces 的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Context Token And Remove Golden Coverage

已实现：

- 新增 context show 与 context repair 的 ordered field-label coverage，包括 moved worktree 回到 registered branch 后的 self-token repair。
- 新增 experiment token list 与 token regenerate 输出的 ordered field-label coverage。
- 新增 inspection checkout create/remove 与 worktree remove/restore 输出的 ordered field-label coverage，包括 dry-run 与 destructive-result 的字段差异。
- 新增 observe log/artifact unarchive 输出 coverage。
- 新增 observe artifact/log/run remove dry-run 与 destructive-result field-order coverage，包括 blocker placement，以及 multi-path run removal plans 中重复 list labels 的契约。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到 project/experiment whole-tree remove、validation remove/archive、annotation edit/archive/remove 和 adapter-specific init surfaces 的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Validation Annotation And Tree Remove Golden Coverage

已实现：

- 新增 validation archive/unarchive 与 validation remove dry-run/destructive 输出的 ordered field-label coverage，包括 blocker placement 与重复 filesystem-path labels。
- 新增 annotation edit、archive、remove dry-run/destructive 输出的 ordered field-label coverage。
- 新增 experiment archive 与 whole-experiment remove dry-run/destructive 输出的 ordered field-label coverage，包括 branch-ref 与 filesystem-removal fields。
- 新增 project archive 与 whole-project remove dry-run/destructive 输出的 ordered field-label coverage。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到 adapter-specific init surfaces、source list/remove、cache/backup prune、key list/revoke 和 project/experiment unarchive variants 的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Key Cache And Unarchive Golden Coverage

已实现：

- 新增 root/admin key list 与 key revoke 输出的 ordered field-label coverage。
- 新增 backup prune 与 cache prune 输出的 ordered field-label coverage，包括 pruned backup paths 和 selected cache kinds 的重复 list labels。
- 新增 removable non-default source lifecycle 路径上 source list 与 source remove dry-run/destructive 输出的 ordered field-label coverage。
- 复用 source status helper 校验 source archive/unarchive 输出。
- 在 whole-tree removal tests 重新归档前，新增 project 与 experiment unarchive 输出 coverage。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到 adapter-specific init surfaces、source warning variants、project init result variants 和 runner adapter result blocks 的 command-by-command fixtures。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Adapter Init And Source Warning Golden Coverage

已实现：

- 新增 SkyDiscover catalog add/show/update/remove 输出的 ordered field-label coverage。
- 新增 adapter-referenced project init 输出的 ordered field-label coverage，覆盖 SkyDiscover catalog validation、SkyDiscover Python/Docker baseline runs、Harbor baseline runs、Harbor-derived source init，以及 SkyDiscover initial-program init。
- 新增 reusable project init、experiment create、source import 和 SkyDiscover catalog field-label helpers，供 CLI golden matrix 复用。
- 新增 experiment create 输出在无 inline-source warning 与带 inline-source warning rows 时的 ordered field-label coverage。
- 新增 source import warning variants 的 ordered field-label coverage，包括 tracked sensitive source files 与 empty-after-filter imports。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到 remaining runner adapter result blocks 和较少见的 config/source edge cases。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_harbor_project_init_uses_declared_source_and_excludes_private_assets tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules tests/test_smoke.py::test_source_import_empty_after_filter_warns -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Runner Adapter Result Golden Coverage

已实现：

- 新增 CLI `run` 输出的 reusable ordered field-label helper，覆盖可选 warning-code rows 与 failure-field suffixes。
- 在 core local workflow 与 host-env warning workflow 中复用该 helper，使 passed runs 和带 warning 的 runs 共用同一输出契约。
- 将 SkyDiscover Python baseline smoke test 延伸到 experiment create 与 CLI `run`，校验 adapter run result block 和 parsed reward 输出。
- 将 SkyDiscover Docker fake-adapter smoke test 延伸到 experiment create 与 CLI `run`，校验 adapter run result block 和 parsed reward 输出。
- 将 Harbor fake-adapter smoke test 延伸到 experiment create 与 CLI `run`，校验 adapter run result block 和 parsed reward 输出。

仍未完成：

- 完整 CLI golden matrix 仍需要继续扩展到较少见的 config/source edge cases 与 failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Failure And Edge Result Golden Coverage

已实现：

- 新增 CLI error blocks、project config set results、project validation results 和 submission failure results 的 reusable ordered field-label helpers。
- 新增 debug-safe saved run failures 的 ordered field-label coverage，确保 persisted `RUNNER_FAILED` 输出保持 normal run summary 后接 failure fields 的结构。
- 新增 submission failure result blocks 的 ordered field-label coverage，包括 rerun failure 与 missing reusable passed-run failure。
- 新增 mutable-scope recorded run errors 与 normal mutable-scope passed runs 的 ordered field-label coverage。
- 新增 representative CLI error blocks，以及 project init、source import、experiment create、manual project validate 的 exact-boundary success outputs 的 ordered field-label coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_stack_trace_only_for_internal_errors tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker Environment Probe

已实现：

- 在运行 opt-in integration coverage 前探测当前 real Docker 环境。
- 确认 Docker CLI 已安装，但当前 session 中配置的 Docker Desktop daemon socket 不可用。
- 使用 `ALAB_RUN_REAL_DOCKER=1` 运行 opt-in real Docker pytest 入口；三个 real Docker tests 都因为 daemon unavailable 而 cleanly skipped，没有误失败。

仍未完成：

- Real Docker runner、Harbor verifier 和 SkyDiscover Docker evaluator execution 仍需要在 Docker daemon 正在运行的环境中重新执行。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `docker version`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py -q`

## 2026-05-19 Baseline Failure Result Golden Coverage

已实现：

- 新增 project init baseline failures 的 ordered field-label coverage，覆盖 project result summary 后接 `BASELINE_VALIDATION_FAILED` fields 的结构。
- 新增 invalid project 上 manual project validation failures 的 ordered field-label coverage。
- 新增 runtime-affecting project config set failures 以及后续 successful recovery config set 的 ordered field-label coverage。
- 扩展 representative stderr error-block coverage 到 old root-key auth denial、command unavailability、context conflict、output-exists export errors，以及 private-safe not-found scope violations。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real Docker runner、Harbor verifier 和 SkyDiscover Docker evaluator execution 仍需要在 Docker daemon 正在运行的环境中重新执行。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Annotation Collaboration Golden Coverage

已实现：

- 新增 annotation add outputs 与完整 annotation observe/show/list blocks 的 reusable ordered field-label helpers。
- 新增 path-target、line-target、experiment-target 和 private annotation creation outputs 的 ordered field-label coverage。
- 新增 filtered annotation list output 与 multi-block sorted annotation list output 的 ordered field-label coverage。
- 新增 annotation show with history 的 ordered field-label coverage，包括 repeated revision rows；同时覆盖 empty-body annotation show output。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real Docker runner、Harbor verifier 和 SkyDiscover Docker evaluator execution 仍需要在 Docker daemon 正在运行的环境中重新执行。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker Integration Validation

已实现：

- 在 Docker Desktop 启动后重新运行 opt-in real Docker integration suite，并确认 daemon 可连接。
- 修正 real Docker test harness：当环境没有显式提供 `DOCKER_CONFIG` 时，使用临时 `DOCKER_CONFIG` 隔离 Docker client state，避免 sandbox 写入用户默认 `~/.docker/buildx/activity` 路径。
- 验证 real Docker runner 路径：使用 Alpine container，挂载 workspace/run directories，并解析 stdout reward。
- 验证 real Harbor shared verifier 路径：使用 Alpine verifier container，覆盖 hidden verifier logs、reward file parsing 和 metrics parsing。
- 验证 real SkyDiscover Docker evaluator 路径：构建 Alpine evaluator image，使用 read-only evaluator mount，覆盖 hidden stderr capture、JSON metric parsing 和 reward extraction。

仍未完成：

- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。
- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。

验证：

- `docker version`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real Docker CLI Workflow Validation

已实现：

- 新增 opt-in real Docker CLI workflow coverage：使用真实 Docker runner 创建 project，通过 `project init` 运行 baseline validation，创建 experiment，并从 experiment worktree 执行 `alab run`。
- 验证 real Docker CLI 路径会写入 run logs，捕获 container 内生成的 `run:` artifact，在 SQLite 中存储 run reward，并存储 baseline validation reward。
- 验证 real Docker 路径的 top-level CLI run output，包括 parsed reward、captured artifact count，以及 `DOCKER_SETUP_OUTPUT_CAPTURED` warning propagation。
- 该测试继续放在 `real_docker` marker 与 `ALAB_RUN_REAL_DOCKER=1` guard 下，普通测试运行仍会跳过外部 Docker execution。

仍未完成：

- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。
- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。

验证：

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py::test_real_docker_cli_project_run_workflow -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache ALAB_RUN_REAL_DOCKER=1 uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 SQLite Migration File And Backup Hardening

已实现：

- 新增从 `src/alab/migrations/` 加载 file-backed SQL migration，首个迁移文件 `1_initial.sql` 由现有 V1 schema 生成。
- 移除 `db.py` 中旧的重复 embedded schema；运行时 schema DDL 现在只保存在 migration SQL files 中。
- `Database.migrate()` 现在会在正常 storage access 前校验 migration filename、连续 schema version、精确 `sha256:<hex>` checksum、unknown applied version、checksum/name mismatch，以及磁盘 schema version 比当前代码更新的情况。
- Migration application 现在使用 ALAB_HOME 级 file lock，将每个 pending migration 作为单个 SQL transaction 应用，并在 `schema_migrations` 中记录精确 migration metadata。
- 在对已有 migrated database 应用 pending migration 前，ALab 现在会通过 SQLite backup API 在 `ALAB_HOME/backups/alab-<from>-to-<to>-<timestamp>.db` 创建一致性备份。
- 新增聚焦 migration tests，覆盖精确 file checksum recording、checksum mismatch rejection、模拟未来 migration 前的 pre-upgrade backup creation、failed-version rollback 和 downgrade rejection。
- 新增 setuptools package data 配置，将 `alab/migrations/*.sql` 纳入构建包，并验证生成的 sdist/wheel 已包含 `alab/migrations/1_initial.sql`。
- 将 project license metadata 更新为 SPDX string 形式，消除 build 时的 setuptools deprecation warning。
- 更新 README 和本地 agent guides，说明 file-backed migration checksum validation 与 pre-upgrade backups。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv build`
- `git diff --check`

## 2026-05-19 Path Hash Case Normalization

已实现：

- 新增 filesystem-aware path hash normalization：只有在底层 filesystem 被检测为 case-insensitive 时，path registry hash 才会对 resolved realpath 做 casefold。
- 检测路径使用已有 path components 和 `samefile` checks，正常 path hashing 过程中不会写入文件系统。
- 新增聚焦 tests，验证 case-insensitive filesystem 上不同大小写 path 会得到相同 hash，而 case-sensitive filesystem 上会保留大小写差异。
- 更新 README 状态说明，记录 path registry 的 case-normalized hashing 行为。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv build`
- `git diff --check`

## 2026-05-19 Public Id Contract Coverage

已实现：

- 新增 public object id suffix generation 的聚焦 tests，锁定文档要求的 22-character unpadded base64url encoding 和 128 bits entropy。
- 新增 `new_id` slug/suffix composition coverage，以及 `require_complete_id` 对 incomplete、padded、too-short 和 too-long suffix variants 的 rejection coverage。
- 新增 slug normalization coverage，覆盖 NFKC input 与 fallback slug。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_ids.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Storage Invariant Coverage

已实现：

- 新增聚焦 storage tests，验证 migration 后 ALab SQLite connections 使用 WAL journal mode。
- 新增 canonical JSON ordering coverage，覆盖 nested dictionaries、compact separators 和 non-ASCII preservation。
- 新增 config hash stability coverage，验证 insertion order 不同但语义相同的 dictionaries 会生成相同 `sha256:<hex>` hash。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Capability Preflight File-Input Guard Coverage

已实现：

- 新增 inspection-context golden coverage，验证 unavailable `submit` commands 会在读取缺失的 `--summary-file` 或 `--feedback-file` paths 之前以 `COMMAND_UNAVAILABLE` 失败。
- 新增 inspection-context golden coverage，验证 unavailable `annotate add` commands 会在读取缺失的 `--body-file` path 之前以 `COMMAND_UNAVAILABLE` 失败。
- 扩展既有 capability help/preflight 场景，使其在先前已覆盖 project secret value file path 的基础上继续覆盖 body/summary/feedback file inputs。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Option Sentinel Coverage

已实现：

- 新增 CLI golden coverage，验证 global pre-scan 在 standalone `--` 之前停止处理 `--key-stdin`，因此该 token 会被当作 command argument，且不会读取 stdin。
- 将该覆盖放入既有 global-option edge 场景，与 post-command global option placement、global-output selection 和 key conflict checks 一起维护。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Error Exit Mapping Contract Coverage

已实现：

- 新增聚焦 tests，锁定每个 registered `*_NOT_FOUND` code 都映射到 exit `2`。
- 新增聚焦 tests，锁定 `PROJECT_INVALID` 与 `COMMAND_UNAVAILABLE` 都映射到 exit `4`。
- 新增聚焦 tests，锁定 runner/reward/baseline result-failure codes 映射到 exit `1`，`OUTPUT_EXISTS` 映射到 exit `2`，unknown internal errors 默认映射到 exit `5`。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_errors.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Credential Storage Contract Coverage

已实现：

- 新增聚焦 credential storage tests，验证 raw admin credential 和 raw secret 不会存入 credential metadata、salt 或 verifier hash。
- 新增 raw credential wire format coverage，确认 raw credential 包含 generated credential id，并可按 credential type 解析。
- 新增 verification tests，覆盖 required credential scope、project binding、token mode binding、token path binding，以及 revoked-token rejection。
- 新增 one-active-root partial uniqueness constraint 的 DDL coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 DDL And Path Registry Contract Coverage

已实现：

- 新增代表性的 SQLite enum `CHECK` coverage，覆盖 credentials、audit events、runs 和 path registry rows。
- 新增 required index presence coverage，覆盖关键 audit、credential、project、config、source、experiment、run、artifact、log、annotation、path registry、lock 和 cache lookup indexes。
- 新增 path registry partial-unique coverage，验证 removed rows 不会阻塞 path reuse，同时重复 active path/hash rows 仍会被拒绝。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Migration Lock Contract Coverage

已实现：

- 新增 interprocess migration test，验证当另一个 process 持有 ALAB_HOME `.migration.lock` file 时，`Database.migrate()` 会被该 lock 阻塞。
- 验证 blocked child process 在 lock 释放前不会创建 SQLite database，并且在 lock 释放后能完成 migration。
- 将 migration-lock behavior 与既有 migration checksum、backup、rollback、downgrade、WAL、DDL 和 path-registry tests 一起锁定。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Worktree Token Uniqueness Coverage

已实现：

- 新增聚焦 credential DDL coverage，验证同一 experiment 只能存在一个 active worktree token。
- 验证 revoked worktree token history 不会阻塞创建 replacement active worktree token。
- 验证同一 experiment 的多个 active inspection tokens 不会被 worktree-token partial unique index 阻塞。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Migration File Validation Coverage

已实现：

- 新增聚焦 migration tests，拒绝文件名不符合 `<version>_<name>.sql` contract 的 `.sql` files。
- 新增聚焦 migration tests，验证 non-contiguous migration version sets 会在任何 database migration 应用前被拒绝。
- 在 checksum mismatch、downgrade rejection、per-version rollback、pre-upgrade backups 和 home-level migration locking 之外，进一步扩展 migration contract coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Text Renderer List And Null Contract Coverage

已实现：

- 扩展 renderer golden test，验证 list fields 会渲染为 repeated labels，而不是 comma-separated scalar fields。
- 新增 coverage 区分 nullable multiline fields（`field: none`）、empty user text（`[empty]`）和作为 indented multiline value 渲染的 literal user text `none`。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_text_renderer_object_block -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Secret Fingerprint And Retain Marker Coverage

已实现：

- 扩展 project secret CLI coverage，验证 plaintext local `secret_values.value` storage，同时 command output、secret list、config show 和 config export 都不会渲染 raw secret value。
- 新增 fingerprint checks，验证 stored HMAC fingerprint 来自 project fingerprint key，并绑定 `secret_env` name 与 value。
- 新增 config export/import coverage，验证 exported retain markers 只包含 retain metadata 与 fingerprint，且不能换到不同的 `secret_env` name 下重用。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Named DDL Table And Column Coverage

已实现：

- 新增 schema-introspection tests，覆盖 V1 点名的 storage surfaces：`experiment_submissions`、`experiment_tags`、`runtime_capabilities`、`catalogs` 和 `cache_entries`。
- 新增 column coverage，覆盖 `projects.secret_fingerprint_key`、`experiments.bound_validation_id`、final-run removal metadata、validation archive columns 和 `annotations.target_json`。
- 将该覆盖与既有 DDL enum、index、migration、path registry 和 token uniqueness coverage 一起维护。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Config Version No-Op And Inheritance Coverage

已实现：

- 扩展 project config lifecycle coverage，验证 repeated no-op `project config set` operations 不会创建额外 config versions。
- 新增 metadata-only config edit coverage，验证会创建新的 `inherited` config version，`active_valid_config_version` 前进到该版本，同时 `active_validation_id` 仍指向证明 unchanged runtime config 的 validation。
- 新增 revert coverage，验证回到旧 canonical config content 会创建新的 monotonic version，并复用已有 `config_hash`，因此 config hashes 不受 unique constraint 限制。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Config Dry-Run No-Write Coverage

已实现：

- 新增 project config dry-run coverage，使用如果真正执行就会失败的 runner commands。
- 验证 `project config set --dry-run` 与 `project config import --dry-run` 都会报告 `validation status: dry-run`，并保持 `latest_attempted_config_version`、`active_valid_config_version` 和 `active_validation_id` 不变。
- 验证 dry-run config set/import changes 不会新增 `project_config_versions`、`project_validations` 或 lifecycle `audit_events` rows。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run Nullable Field DDL Coverage

已实现：

- 新增 storage DDL coverage，验证 `running`、`error` 和 `interrupted` run rows 可以在 `exit_code`、`reward_value` 和 `ended_at` 为 null 的情况下存储。
- 将该覆盖与既有 run enum checks、archive status checks、run index coverage 和 run lifecycle smoke tests 一起维护。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Secret GC Candidate And Audit Coverage

已实现：

- 扩展 project secret coverage，构造明确未引用的 local secret value，用于验证 GC candidate calculation。
- 验证 `project secret gc --dry-run` 会报告 candidate，但不会渲染 raw secret value、删除 rows 或写入 audit events。
- 验证 `project secret gc --apply` 只删除未引用的 secret value，保留 referenced active secret，并写入 `secret_value` 的 `gc` audit event。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Remove Dependency Coverage

已实现：

- 完成 `source remove` 对 dependent experiments 的 lifecycle enforcement。
- `source remove` 现在会在存在 dependent experiments 且未提供 `--cascade` 时阻塞；即使提供 `--cascade`，也要求所有 dependent experiments 都已 archived。
- Source removal 现在会删除对应的 Git source ref；如果 database update 失败，会恢复该 ref。
- 扩展 smoke coverage，验证 dependent experiments 会被保留、archived dependency requirements 会被执行，并验证已删除 source ref 在 project repository 中不存在。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit State Gate Coverage

已实现：

- 为 `submit` 增加与 V1 contract 一致的显式 state checks：project 不能 archived，experiment 必须 open，且 experiment worktree state 必须 active。
- 修复 reusable passed-run 路径可绕过 `_run_experiment()`、进而跳过这些 state checks 的问题。
- 扩展 local run/submit smoke workflow，验证接受 reusable passed run 之前会正确拒绝 `PROJECT_ARCHIVED`、removed worktree state 的 `SCOPE_VIOLATION` 以及 `EXPERIMENT_CLOSED`。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Project Exp Create Error Code

已实现：

- 调整 `exp create`，使 archived project 返回 `PROJECT_ARCHIVED`，而不是通用的 `PROJECT_INVALID`。
- 新增 explicit admin-key path 的 smoke coverage；该路径会通过 capability preflight 进入 handler，并验证文档规定的 archived-project error code。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Stale Lock Clear Positive Coverage

已实现：

- 扩展 `project locks clear-stale` smoke coverage，在同一个 project 中构造一个 expired lock 和一个 live lock。
- 验证命令只报告 expired lock name，只删除 expired lock row，保留 live lock row，并为 `lock` 写入带 `cleared_count` 的 `clear` audit event。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Target Not Archived Blocker Contract

已实现：

- 按 lifecycle contract 统一 hard-remove dry-run 与 actual-remove blocker，使用稳定的 `target_not_archived`，不再使用 `project_not_archived`、`source_not_archived`、`experiment_not_archived`、`run_not_archived`、`artifact_not_archived`、`log_not_archived`、`validation_not_archived` 或 `annotation_not_archived` 等 object-specific names。
- 扩展 source、run、artifact、log、annotation、experiment 和 project remove dry-runs 的 smoke coverage，验证 active targets 会渲染 `target_not_archived`。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Remove Cascade Argument Contract

已实现：

- 执行文档规定的 `project remove` 参数要求：dry-run 和 actual removal 都必须提供 `--cascade`。
- 保持 `--reason` validation 位于 cascade check 之前，因此 oversized reason text 仍会走文本长度相关的 `CONFIG_INVALID` 路径。
- 新增 smoke coverage，验证 `project remove --dry-run` 缺少 `--cascade` 会以 `CONFIG_INVALID` 和稳定的 cascade-required message 失败。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hard Remove Confirmation Guard Coverage

已实现：

- 新增共享 smoke-test assertion，用于验证 destructive remove confirmation guards。
- 扩展 missing `--force`、missing `--confirm`、wrong confirmation values 的覆盖，范围包括 SkyDiscover catalog remove、validation remove、source remove、inspection checkout remove、experiment worktree remove、annotation remove、experiment remove、project remove、artifact remove、log remove 和 run remove。
- 每个断言都放在成功 actual remove path 之前，并确保目标已经处于 dependency-ready state，因此测试验证的是 confirmation guard，而不是无关的 lifecycle blockers。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archive Idempotence Audit Coverage

已实现：

- 收紧 archive/unarchive idempotence：重复 archive 会复用已存储的 archive timestamp，不再渲染新的 timestamp；重复 unarchive 在没有状态迁移时渲染 `none`。
- validation、run、artifact 和 log 在 unarchive 状态迁移时会清空 `archived_at`，因此之后真正再次 archive 会记录新的 archive timestamp；而 no-op archive 会保留已有 timestamp。
- 新增 smoke coverage，验证 project、validation、source、experiment、run、artifact、log 和 annotation lifecycle surfaces 的重复 archive/unarchive 不会创建 duplicate audit rows。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Actual Remove Not-Archived Error Coverage

已实现：

- 新增共享 smoke-test assertion，用于验证 unarchived targets 上的 actual destructive remove attempts。
- 扩展 validation、source、log、artifact、annotation、experiment、project 和 run removal paths 的覆盖，验证它们会以 `RESOURCE_BUSY` 失败，渲染稳定的 `target_not_archived` blocker，并且不会创建 `remove` audit row。
- 该覆盖与 dry-run coverage 分开，因此 V1 contract 现在同时验证 non-mutating planning output 与受保护的 destructive path。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Remove Dry-Run No-Write Coverage

已实现：

- 新增共享 smoke-test assertion，验证 remove dry-runs 不会创建 `remove` audit rows，也不会删除目标的 authoritative database row。
- 扩展 validation、source、log、artifact、annotation、experiment、project 和 run hard-remove paths 的 dry-run preservation coverage；在已有状态允许时，同时覆盖 blocked 与 dependency-ready dry-run cases。
- 为 worktree 和 inspection checkout dry-run 增加明确的 preservation checks，验证 filesystem 仍存在，并且 token/path/experiment state 保持 active，因为这些命令在 actual removal 中会 staging filesystem 与 credential mutations。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Actual Cascade Blocker No-Mutation Coverage

已实现：

- 新增共享 smoke-test assertion，用于验证被 lifecycle dependency blockers 拦截的 actual destructive remove attempts。
- 扩展 validation、source 和 run removal coverage：no-cascade `dependent_records_require_cascade` blockers 与 active-child `dependent_records_not_archived` cascade blockers 都会返回 `RESOURCE_BUSY`，且不会创建 `remove` audit rows。
- 验证被拦截路径在进入成功 archived-dependency removal path 之前，会保留 target rows、dependent rows、filesystem artifacts/logs，以及适用场景下的 source Git ref。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Active Lock Archive And Remove Guard Coverage

已实现：

- 新增 smoke helpers，用于插入和清理 deterministic active lifecycle locks。
- 扩展 experiment lifecycle coverage，验证 active experiment lock 存在时，`exp archive` 和 actual `exp remove --cascade` 会以 `RESOURCE_BUSY` 失败，不写 archive/remove audit rows，也不删除 filesystem/Git state。
- 扩展 project lifecycle coverage，验证 active project lock 存在时，`project archive` 和 actual `project remove --cascade` 会以 `RESOURCE_BUSY` 失败，不写 archive/remove audit rows，也不删除 project/control/worktree/inspection paths。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Worktree Restore Guard Coverage

已实现：

- 新增 smoke coverage，验证 experiment 仍有 active worktree 时，`exp worktree restore` 会以 `RESOURCE_BUSY` 失败，并且不会创建请求的 restore path 或写入 restore audit rows。
- 新增 non-empty destination coverage，验证 restore 会以 `OUTPUT_EXISTS` 失败，并且在失败前不会写入 `.alab` metadata、创建 token/path registry row、修改 `worktree_state` 或写入 restore audit rows。
- 保留这些失败检查之后的既有 successful restore path，因此测试仍验证目标合法时 marker/token creation 与 active worktree state。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Worktree Restore Nesting Guard Coverage

已实现：

- 新增 direct restore path nesting coverage，覆盖位于已有 experiment context 内部的 `exp worktree restore` 目标路径。
- 验证 nested restore attempt 会以 `CONTEXT_CONFLICT` 失败，不会创建请求的 nested path，也不会写入 restore audit row。
- 将该覆盖与 active-worktree 和 non-empty-destination restore guards 放在一起，使 restore preflight 分别覆盖 context nesting、active state 与 destination occupancy。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Inspection Checkout Path Guard Coverage

已实现：

- 新增 inspection checkout creation preflight coverage，覆盖嵌套在已有 experiment context 内部的目标路径。
- 新增 non-empty inspection checkout destination coverage，验证 checkout 会在写入 `.alab` metadata、创建 inspection token/path registry row 或写入 `inspection_checkout` add audit row 前失败。
- 验证这些 guarded failures 之后的 successful checkout path 仍只创建一个 add audit row。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Dedupe Archived-Source Coverage

已实现：

- 新增聚焦 smoke coverage，验证 active source content dedupe：第二次导入相同 canonical tree hash 时会返回 existing source id/ref，并且不会写入第二条 source add audit row。
- 验证 deduped import 会追加 sanitized `origin_metadata_json.origins` entries，不存储 local source paths，同时保留原始 `primary_origin`。
- 覆盖 explicit-name mismatch 行为，断言会渲染 `SOURCE_DEDUPED_NAME_IGNORED`，并将该 warning 存入追加的 origin entry。
- 新增 standalone root/admin source name slug conflict coverage，验证不同 tree 但 normalized name 相同的导入会在写入 source rows 或 add audit rows 前以 `NAME_CONFLICT` 失败。
- 验证 archived sources 不参与 dedupe lookup：旧 source archive 后，相同内容重新 import 会创建新的 active source，tree hash 相同但 id/ref 不同。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Selector Option Scope Guard

已实现：

- 新增共享 source option scope validation，使 `--git-ref` 在 project init、standalone source import 和 experiment inline source creation 中都只允许与 `--source-git` 搭配使用。
- 新增共享 `--source-subdir` scope validation，使其只允许与 `--source-path` 或 `--source-git` 搭配，同时保留 `--source-subdir conflicts with --source-empty` 这个 specific error。
- 新增 smoke coverage，验证 invalid standalone source import 与 experiment creation option combinations 会在写入 source/experiment rows、创建 experiment worktrees 或写入 add audit rows 前以 `SOURCE_INVALID` 失败。
- 在 shared preflight change 后，重新检查 valid public inline local/Git source import 与 active-source dedupe coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_rejects_runtime_flags tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Public Experiment Name Conflict Coverage

已实现：

- 扩展 public no-key experiment creation coverage，验证 normalized experiment name slug conflicts 会以 `NAME_CONFLICT` 失败。
- 验证重复 public create attempt 不会创建请求的 worktree path，不会插入 experiment row，也不会写入 experiment add audit row。
- 保留同一测试中已有的 public `--from-exp` latest-commit inheritance path，因此 duplicate-name guard 不会削弱 successful inheritance coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Source Explicit Experiment Creation

已实现：

- 更新 `exp create --source-ref`，当调用方显式指定 source ref 时解析 retained source rows，而不是在所有场景都强制 source 必须 active。
- 保留 implicit default-source experiment creation 的 active-only 要求。
- 强制 V1 rule：从 archived source 创建新 experiment 需要 root/admin credentials；public no-key creation 会在写入 experiment rows、audit rows 或 worktree files 前被拒绝。
- 新增 smoke coverage，验证 root/admin 可以从 archived source ref 创建 experiment，新 worktree 来自 archived source commit，并且 source 仍保持 archived。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_admin_exp_create_can_bind_archived_source_ref -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived From-Experiment Inheritance Coverage

已实现：

- 扩展 public `--from-exp` coverage，在验证 ordinary public latest-commit inheritance 成功后 archive source experiment。
- 验证 public no-key 从 archived source experiment 继承会以 `SCOPE_VIOLATION` 失败，并且在失败前不会创建 worktree、插入 experiment row 或写入 experiment add audit row。
- 验证 root/admin 仍可从 archived source experiment 创建新 experiment，并具有预期 latest baseline commit、`from_exp` metadata，且不会创建新的 source row。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 From-Commit SHA Selector Guard

已实现：

- 收紧 experiment commit selector resolution，使 custom selectors 必须是 SHA-like values；`HEAD` 等 arbitrary Git refs 不再可作为 V1 `--from-commit` 或 checkout commit selector。
- 保留 named selectors `latest`、`final`、`best`，并继续对 SHA selectors 执行 source experiment branch reachability checks。
- 扩展 public `--from-exp` coverage，验证 non-SHA `--from-commit HEAD` 会以 `CONFIG_INVALID` 失败，并且在失败前不会写入 experiment rows、audit rows 或 worktree files。
- 新增 public full-SHA `--from-commit` success coverage，验证新 experiment 会存储 requested selector 和 resolved commit，且不会创建新的 source row。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Public From-Commit Final And Best Coverage

已实现：

- 扩展 public `--from-exp` coverage：先用 `submit` close source experiment，再分别用 `--from-commit final` 和 `--from-commit best` 创建 children。
- 新增 no-write failure coverage，覆盖没有 qualifying run 时的 `--from-commit best`，以及 source experiment 尚无 final commit 时的 `--from-commit final`。
- 验证 `final` 会解析到 closed experiment 的 stored final commit，保留 `from_exp` metadata，并且不会创建新的 source row。
- 验证 `best` 会通过 active reward policy 的 best-run selection 解析，存储 `from_commit: best` 与 resolved commit，并保留相同 source lineage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Inspection Checkout Commit Selector Guard

已实现：

- 扩展 inspection checkout preflight coverage，使 `exp checkout --commit HEAD` 作为 non-SHA custom selector 被拒绝。
- 验证 invalid checkout selector 会在创建 checkout directory、inspection token/path rows 或 `inspection_checkout` add audit row 前以 `CONFIG_INVALID` 失败。
- 保留同一流程中的 successful `--commit latest` checkout，验证 guarded failures 后 valid selector 仍只创建一个 inspection checkout。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Annotation Commitish Alias Resolution

已实现：

- 将 annotation target commitish handling 与 strict experiment creation/checkout selector handling 分开，使 annotation targets 仍可使用文档规定的 `HEAD`/`head` aliases。
- 新增 `path:<exp_id>@HEAD:<repo_path>`、`lines:<exp_id>@best:<repo_path>:<range>` 和 `path:<exp_id>@final:<repo_path>` smoke coverage，验证 annotation aliases 会在 creation time resolve 为 concrete commits。
- 验证 stored annotation `target_id`、`target_json.commit` 和 `resolved_commit` 都保存 concrete commit SHA，而不是 moving alias。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project-Context Annotation Shorthand Rejection Coverage

已实现：

- 新增 smoke coverage，验证 `path:<repo_path>` shorthand 在 project/admin context 中会被拒绝，因为它不能确定 exactly one experiment。
- 验证被拒绝的 project-context annotation target 不会写入 `annotations` 或 `annotation_revisions` rows；随后测试回到 experiment context 并成功创建 shorthand path annotations。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Regenerated Token Private Annotation Coverage

已实现：

- 扩展 regenerated worktree token coverage，显式 show 并 edit 由同一 experiment 之前 token 创建的 experiment-private annotation。
- 验证 private annotation ownership 是 experiment-bound，而不是 raw-token-bound：regenerated token edit 会创建 revision 3。
- 更新 annotation remove dry-run/actual checks 与 audit metadata assertions，确保新的 revision count 在 hard removal 中保持一致。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Invalid Project Active-Valid Preservation

已实现：

- 当后续 runtime-affecting config 被 skip、baseline validation 失败、manual `project validate` 失败，或 stale validation 被中断时，保留 `projects.active_valid_config_version` 和 `projects.active_validation_id`。
- invalid projects 仍通过 capability resolver 阻止 experiment creation，同时允许只读 observe/best flows 使用之前 active-valid reward policy identity。
- 新增 smoke coverage，验证 `--skip-baseline-test` 后 `project config show --version active-valid` 仍可用，failed manual validation 会保留 previous active validation，且后续 runtime config attempt 失败后 `observe experiments best` 仍按 active-valid identity 排名。
- 更新 stale-running validation coverage，验证 stale cleanup 会将 project 标为 invalid，但不会丢弃已经证明过的 active-valid config reference。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Experiment Observe Visibility Coverage

已实现：

- 扩展 experiment ranking/search smoke coverage，加入一个 reward 优于当前 active best experiment 的 archived experiment。
- 验证 archived experiments 默认会从 `exp list`、`exp search` 和 `observe experiments best` 中隐藏。
- 验证 `--include-archived` 会在 list/search output 中显式纳入 archived experiments，并允许 `best` 在请求时对 archived comparable run 排名。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Observe Authorization Coverage

已实现：

- 扩展 Harbor smoke flow，在 successful adapter run 后通过 public observe/log CLI surface 覆盖 hidden verifier logs。
- 验证 worktree tokens 不能 show hidden logs，也不能通过 `logs export --include-hidden` 绕过限制；被拒绝的 export 不会写 output file。
- 验证 root/admin callers 也必须显式使用 `--include-hidden` 才能 show hidden log；`logs list` 默认隐藏 hidden streams，只有请求时才纳入。
- 验证 root/admin hidden-log export 写出 exact stored bytes，而这些 bytes 在 storage 前已经完成 secret redaction。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment Search Corpus Boundary Coverage

已实现：

- 扩展 experiment search/ranking smoke coverage，使 runner stdout、runner stderr 和 captured artifact bytes 都包含唯一 search needles，并验证它们不会出现在 `exp search` results 中。
- 新增 current-vs-historical annotation coverage：current annotation body 仍可被搜索，已被新 revision 取代的 historical annotation body 会被 search corpus 排除。
- 保留同一 flow 中已有的 private-annotation search visibility checks，使 search 同时覆盖 allowed text、private visibility 与 excluded storage surfaces。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Regenerated Token Lifecycle Permission Coverage

已实现：

- 扩展 regenerated worktree token smoke flow，使 restored/regenerated token 能 archive 和 unarchive 自己 experiment 的 run、captured artifact 与 visible stdout log。
- 在 collaboration fixture 中新增 run artifact，使 artifact lifecycle permission 与 run/log lifecycle permissions 一起被覆盖。
- 验证每个 regenerated-token archive/unarchive operation 都渲染预期 status transition，并为对应 object type 只写入一个 audit event。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Lifecycle Permission Coverage

已实现：

- 扩展 Harbor hidden-log smoke flow，在 hidden-log show/list/export checks 后继续覆盖 lifecycle permissions。
- 验证 worktree token 不能 archive hidden log，且被拒绝的操作不会改变 log archive status，也不会写 audit log。
- 验证 root/admin 可以通过 id archive 和 unarchive hidden log，并产生预期 status transitions 与每个 transition 一个 audit event。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Remove Coverage

已实现：

- 将 Harbor hidden-log lifecycle smoke flow 扩展到 hard remove。
- 验证 experiment context 不能 remove hidden log，且被拒绝的 command 不会改变 log row、file 或 remove audit state。
- 验证 root/admin hidden-log remove dry-run 在 log 仍 active 时报告 `target_not_archived`、planned trash staging，并且不进行 filesystem mutation。
- 验证 root/admin 可以 remove archived hidden log，通过 trash flow 删除 file-backed bytes，并删除 SQLite row，同时写入一个 remove audit event。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Annotation List Created-By And Archive Coverage

已实现：

- 扩展 annotation list smoke coverage，覆盖 `--created-by` 命中 creator experiment id，以及 creator 不匹配时返回空列表。
- 验证 archived annotations 默认不会出现在 list output 中，并且会在带 `--include-archived` 时重新出现。
- 将 checks 保持在 regenerated-token/private-annotation flow 中，从而一起覆盖 ownership、current-revision query filtering 与 archive visibility。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run Failure Reason Observe Coverage

已实现：

- 规范化 run 与 validation records 中保存的 runner failure reasons，使非零退出的 local runner 存储和 CLI result-failure output 一致的 `runner exited with code N` reason。
- 修正 CLI exit-code inference：只读 observe/list/show blocks 如果只是展示 failed saved runs，不再退出 `1`；只有带 `error code` fields 的实际 saved result-failure response 才返回 failure exit。
- 新增 smoke coverage，验证 `runs list --failure-reason-query` 可以通过规范化 reason 找到 failed saved run，且非匹配 reason 返回空列表并成功退出。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Run List Filter Contract Coverage

已实现：

- 扩展 run observe smoke coverage，覆盖 `--config-version`、`--commit`、`--reward-min`、`--reward-max`、`--started-after`、`--started-before`、`--ended-after` 和 `--ended-before`。
- 验证组合的 exact-bound filters 仍会返回预期 run，并保持稳定的 run list field ordering。
- 增加空结果检查：reward lower bound 与 future started-time filter 都能排除 saved run，且 command 成功退出。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Artifact And Log List Filter Coverage

已实现：

- 扩展 log list smoke coverage，围绕 saved stdout log 覆盖 `--created-after` 与 `--created-before`，并增加 future timestamp 空结果检查。
- 扩展 artifact list smoke coverage，在既有 exp/run/root/status/path/size-min filters 基础上组合覆盖 `--content-hash`、`--size-max`、`--created-after` 和 `--created-before`。
- 增加 nonmatching artifact content hash 与 future artifact timestamp 的空结果检查。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Validation Artifact And Log Filter Coverage

已实现：

- 新增 observe coverage，通过 `artifacts list --validation <validation_id>` 验证 baseline validation artifact records。
- 新增 observe coverage，通过 `logs list --validation <validation_id> --stream stdout` 验证 baseline validation log records。
- 验证 incomplete validation selectors 在列出 validation artifacts 前会被拒绝。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Artifact And Log List Coverage

已实现：

- 新增 log list coverage，验证 archived visible logs 默认隐藏，并会在带 `--include-archived` 时返回。
- 新增 artifact list coverage，验证 archived artifacts 默认隐藏，并会在带 `--include-archived` 时返回。
- 将 checks 放在 archived show/export assertions 附近，使 list、show、export 的 archived semantics 一起被覆盖。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Archived Run List Coverage

已实现：

- 新增 run list coverage，验证 archived runs 默认不会出现在 list output 中。
- 验证 `runs list --include-archived` 会返回 archived run，并保留 saved run status。
- 验证 archived run 在 hard remove 前仍可被 authorized admin 通过 id show。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment List And Search Filter Coverage

已实现：

- 扩展 experiment list smoke coverage，覆盖 `--source-id`、`--name-query`、`--config-version`、`--created-after`、`--created-before`、`--updated-after` 和 `--updated-before`。
- 验证 incomplete `--source-id` selectors 在 experiment listing 前会被拒绝。
- 新增 experiment search 的 `--reward-max` coverage，补齐既有 reward minimum filtering 的另一侧。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment Best Filter Coverage

已实现：

- 扩展 experiment best smoke coverage，覆盖显式 `--config-version` 选择。
- 新增 `exp best --reward-max` coverage，验证过滤掉更高 reward 后仍可选出较低排名但合格的 run。
- 新增 `exp best --reward-min` 空结果 coverage，验证没有 qualifying run 满足下界时成功返回空结果。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe Pagination Coverage

已实现：

- 新增 experiment list 的 `--limit` 加 `--offset` smoke coverage，并配合 reward sorting 验证分页。
- 新增 search pagination coverage，使用同一稳定 reward ordering。
- 新增 best pagination coverage，以及 `--limit 0`、`--limit 501` 和负数 `--offset` 的 invalid pagination boundary checks。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe List Pagination Coverage

已实现：

- 新增 focused smoke coverage，覆盖 runs、artifacts、logs 与 annotations 的 observe list pagination。
- 验证 `runs list`、`artifacts list`、`logs list` 与 `annotations list` 会在 deterministic sorting 之后应用 pagination。
- 验证共享 observe pagination parser 会用 `CONFIG_INVALID` 拒绝非整数 `--limit` 值。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_observe_list_pagination_contracts -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Backup Prune Selector Coverage

已实现：

- 扩展 root/auth smoke coverage，覆盖 `backup prune` selector validation。
- 验证 `backup prune --older-than <days>` 只清理 stale backup files，并保留 fresh backups。
- 验证 missing selectors、conflicting `--keep` plus `--older-than`、non-integer `--keep` 和 negative `--older-than` 会以 `CONFIG_INVALID` 失败，且不会清理 backups。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Cache Prune Selector Coverage

已实现：

- 扩展 cache prune smoke coverage，覆盖 V1 selector matrix。
- 验证 `cache prune --trash --older-than <days>` 只移除 stale active trash cache entries，并保留 fresh trash cache entries。
- 验证 `--trash-all` 会在 age-filtered prune 后移除剩余 fresh trash entry。
- 验证 missing selectors、`--all` conflicts、trash selector conflicts、missing `--older-than`、unsupported `--older-than` placement 和 non-integer `--older-than` 会以 `CONFIG_INVALID` 失败，且不会删除 trash paths。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project List Archived Visibility Fix

已实现：

- 修复 `project list`，使 archived projects 默认隐藏，只有使用 `--include-archived` 时才返回。
- 新增 lifecycle smoke coverage，验证 project 在 archive 前出现在 root `project list` 中，archive 后从默认 list 消失，并且仍可通过 `--include-archived` 查看。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Archive Visibility Coverage

已实现：

- 新增 smoke coverage，验证 `source archive` 会用 `RESOURCE_BUSY` 拒绝 active default source，且不会写 archive audit event。
- 新增 source list visibility coverage，验证 archived non-default sources 默认隐藏，并可通过 `--include-archived` 返回。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe Lifecycle Own-Experiment Permission Fix

已实现：

- 收紧 run/artifact/log archive 与 unarchive handlers，使 token callers 只能修改自己实验内 records 的 lifecycle state。
- 保留更宽的 same-project observe read visibility，同时用不泄露对象存在性的 `SCOPE_VIOLATION` 阻断跨实验 lifecycle mutation。
- 修复 ranking/search smoke fixture，使其声明的 `run:` artifact 实际写入 `ALAB_RUN_DIR` 并被捕获为 artifact。
- 新增 coverage，验证 token 可以 show 一个可见的 same-project experiment，但不能 archive 或 unarchive 该其它实验的 run、artifact 或 visible log。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Import Limit Atomicity Coverage

已实现：

- 为 smoke tests 新增 source-ref inspection helper，使 source import failure 能针对 canonical Git refs 断言，而不仅检查 SQLite rows。
- 新增 standalone `source import` 对 max-files、max-file-bytes 和 max-total-bytes failures 的 limit-failure coverage，验证 `SOURCE_LIMIT_EXCEEDED` 不会留下新的 source row、failed source name、新的 `alab/source/*` Git ref 或新的 source add audit event。
- 新增 public inline `exp create --source-path` coverage，验证 no-key callers 不能将任何 source import limit 提高到 `[public_source_import]` policy 之上，并验证 policy-ceiling 与 policy-exceeded failures 都不会留下 source row、experiment row、Git source ref、source add audit 或 worktree path。
- 新增 public inline source-name conflict coverage，验证 derived source names 会得到 deterministic source-id suffix，而不是以 `NAME_CONFLICT` 失败，同时 normalized slug 保持唯一。
- 新增 disabled public source-import policy coverage，验证 public no-key `exp create` 使用 default source 仍可工作，public no-key inline source import 需要 admin/root credentials 且不会产生 partial writes，而 admin inline source import 仍被允许。
- 新增 public inline `--source-empty` coverage，验证 explicit empty-source creation 不会渲染 empty-filter warning，会存储无 warnings 的 empty origin metadata、创建空 source tree，并记录 inline-source experiment provenance。
- 新增 public inline source dedupe coverage，验证 no-key inline import 的 tree 与 active source 相同时会复用已有 source id/ref、追加无 warnings 的 origin metadata、不创建新的 Git source ref，并仍记录 inline-source experiment provenance。
- 新增 public inline local `--source-subdir` coverage，验证只导入被选择的 subdirectory，parent/outside files 不进入 worktree 或 source ref，并且 origin metadata 只存结构化 `source_subdir`，不存 raw source paths。
- Git source origin metadata 现在会记录 resolved upstream commit，并新增 public inline Git coverage，验证显式 `--git-ref` 与省略 `--git-ref` 的 remote-HEAD import 都会保存结构化 `git_ref`、`resolved_commit` 与 `source_subdir` metadata，不存 raw Git URLs，同时保留 credential-helper warnings。
- 新增 public inline Git `--source-subdir` coverage，验证只导入被选择的 Git subdirectory。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_standalone_source_import_limit_failure_is_atomic -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Active Validation Lifecycle Blocker Coverage

已实现：

- 扩展 validation lifecycle smoke coverage，验证当前证明 `projects.active_valid_config_version` 的 validation 不能被 archived。
- 新增 dry-run 与 forced `project validation remove --cascade` coverage，验证 active validation 会渲染稳定 blockers、不写 remove audit、仍保持为 project `active_validation_id`，且保持 unarchived；forced path 会以 `RESOURCE_BUSY active_validation` 被阻断。
- 在同一个 fixture 中保留既有 non-active validation archive/unarchive/remove cascade coverage，用于锁定 removable historical validations 与 active validation proof 的差异。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hidden Log Unarchive Permission Coverage

已实现：

- 扩展 Harbor hidden-log lifecycle coverage，验证 worktree token 在 root/admin archive hidden log 后不能 unarchive 该 hidden log。
- 验证 token path 返回不泄露对象存在性的 `SCOPE_VIOLATION`、不写 unarchive audit，并保持 hidden log 为 archived，直到 root/admin unarchive。
- 将这项 coverage 与既有 hidden-log show/export/list/archive/remove checks 放在一起，覆盖完整 hidden-log lifecycle permission surface。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Public History Preflight Coverage

已实现：

- 扩展 public `exp create --from-exp` smoke coverage，验证即使允许 public inheritance，public no-key history observation 仍会被拒绝。
- 验证 public no-key `observe experiments show` 与 `runs list` 会在 capability preflight 阶段以 `COMMAND_UNAVAILABLE` 失败，而不是进入 handler 并泄露 visibility 细节。
- 验证 public no-key `exp checkout` 会在创建 inspection worktree 或 audit row 之前被拒绝，使 checkout/history access 按 spec 保持 token-bound。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Removed Experiment Archive Flag Coverage

已实现：

- 更新 `cmd_exp_archive`，对已移除的 V1 worktree-removal flags `--remove-worktree` 和 `--force-remove-worktree` 返回 `CONFIG_INVALID`。
- 扩展 experiment removal smoke coverage，验证这些 flags 不会 archive experiment、不写 archive audit row，并将调用者引导到显式的 `exp worktree remove` command。
- 在同一个 lifecycle fixture 中保留既有 active-lock 与 idempotent archive/unarchive checks，使 removed-flag rejection 与真正的 archive state transitions 保持区分。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Runtime Flag Rejection

已实现：

- 新增 `project init` runtime-flag guard，使 V1 init 对 runner、reward、artifact、log、env、secret、Docker、Harbor 和 SkyDiscover override-style flags 返回 `CONFIG_INVALID`，而不是静默忽略。
- 保持 source bootstrap flags、source limits、display overrides 和 `--skip-baseline-test` 作为 mode 与 `--config` 之外唯一接受的 init-time options。
- 新增 smoke coverage，验证这些 runtime flags 被拒绝后不会留下 project rows、source rows 或生成的 admin credentials。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_rejects_runtime_flags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Source Ref Mismatch Cleanup

已实现：

- 修复 `project init` staging cleanup：当 config 提供的 `source.default_source_ref` 与 staged canonical source ref 不匹配，且尚未写入 visible project rows 时，会清理已准备好的 final project path 与 control path。
- 增加初始 project/source/config/admin transaction 是否已提交的状态跟踪，在 rows 成为 authoritative 后保持 retained-project baseline semantics，同时继续清理 pre-commit staging failures。
- 新增 smoke coverage，验证 mismatched source ref 返回 `CONFIG_INVALID`、不写 project/source/config/admin rows，并保持 `projects/`、`project-workspaces/` 与 init staging directory 为空。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_rejects_runtime_flags tests/test_smoke.py::test_project_init_source_ref_mismatch_cleans_staged_paths -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit Stdin Option Rejection

已实现：

- 为 `submit` 新增显式 preflight rejection，拒绝 V1 不支持的 stdin options `--summary-stdin` 和 `--feedback-stdin`。
- 即使调用者同时提供了 otherwise-valid `--summary` 和 `--feedback` values，submit input handling 仍限定为 direct text 或 file inputs。
- 扩展 submit failure/input smoke coverage，验证 stdin options 返回 `CONFIG_INVALID`，并且不会创建 run records。
- 增加匹配的 `annotate` coverage 与 handler rejection，拒绝不支持的 `--body-stdin`，并验证 add 不写 annotation/revision rows，edit 不推进 `current_revision`。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Gitlink Source Rejection Next Action

已实现：

- 为共享 Git submodule/gitlink rejection 增加文档要求的 next action，提示调用者在 import 前 vendor 或 expand submodule contents。
- 扩展 source fidelity smoke coverage，加入真实 Git index gitlink fixture。
- 验证 `source import` 会以 `SOURCE_INVALID` 拒绝 gitlink、不写 source row、不创建 source add audit row，并保持 project Git source refs 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Source Origin Requirement

已实现：

- 收紧 `project init local|git|empty`：每种 mode 都必须提供显式 source origin flag（`--source-path`、`--source-git`、`--source-empty`），缺失 origin 时统一返回 `SOURCE_INVALID`。
- 保持 source-origin conflicts 继续走现有 `SOURCE_INVALID` 路径，同时避免 mode-specific missing origins 落入通用 required-option failure。
- 新增 smoke coverage，验证缺失 mode-specific source origins 不写 project/source/config/admin rows，并保持 ALab project/control/staging paths 为空。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Source Import Existing Selector Rejection

已实现：

- 收紧 `source import`：既有 source 与 experiment inheritance selectors（`--source-ref`、`--from-exp`、`--from-commit`）现在会以 `SOURCE_INVALID` 显式拒绝，不再在旁边存在真实 import origin 时被静默忽略。
- 保持 standalone `source import` 只接受文档定义的 creation origins：`--source-path`、`--source-git` 或 `--source-empty`。
- 扩展 source selector smoke coverage，验证这些 rejected existing selectors 不写 source rows、experiment rows，也不写 source/experiment add audit rows。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate Source Origin Rejection

已实现：

- 收紧共享 source-origin parsing：重复 origin options 现在会按多个 origins 计数，不再被 first-value lookup 折叠。
- `project init`、standalone `source import` 与 inline `exp create` 现在会以 `SOURCE_INVALID` 拒绝重复 source selectors，例如重复 `--source-path` 或重复 `--source-ref`。
- 扩展 smoke coverage，验证 duplicate origin rejection 会让 init 保持 project/source/config/admin rows 不变，也让 source import 与 experiment creation 保持 source/experiment rows 以及 add audit rows 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate From-Experiment Origin Rejection

已实现：

- 收紧 `exp create`：重复 `--from-exp` values 现在会被视为 duplicate source origins，并以 `SOURCE_INVALID` 拒绝。
- 保留 public `--from-exp` inheritance path，同时阻止 first-value lookup 静默丢弃后续 origin selectors。
- 扩展 from-experiment smoke coverage，验证 duplicate `--from-exp` 不创建 worktree、不写 experiment rows，也不写 experiment add audit row。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate From-Commit Selector Rejection

已实现：

- 为 source/experiment selector validation 增加共享 option occurrence counting。
- 收紧 `exp create --from-exp`：重复 `--from-commit` values 现在会以 `CONFIG_INVALID` 失败，不再静默使用第一个 selector。
- 扩展 from-experiment smoke coverage，验证 duplicate `--from-commit` 不创建 worktree、不写 experiment rows，也不写 experiment add audit row。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Secret Duplicate Input Rejection

已实现：

- 收紧 `project secret set` input validation：重复 `--value-file` 或重复 `--value-stdin` 现在会按文档中的 exactly-one input contract 以 `CONFIG_INVALID` 失败。
- 复用 shared option occurrence counting，使 secret path 不再依赖 first-value lookup 处理 mutually exclusive input options。
- 扩展 secret input smoke coverage，验证 duplicate input options 不写 `secret_values`、不创建 project config version，也不写 audit rows。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Submit And Annotation Duplicate Input Rejection

已实现：

- 为具有 exactly-one CLI contract 的 text input pairs 复用 shared option occurrence counting。
- 收紧 `submit`：重复 `--summary`、重复 `--summary-file`、重复 `--feedback` 或重复 `--feedback-file` 现在会在 file reads 或 runner execution 前以 `CONFIG_INVALID` 失败。
- 收紧 `annotate add|edit`：重复 `--body`、重复 `--body-file` 或混合 body inputs 现在会在 body file reads 或 annotation revision writes 前以 `CONFIG_INVALID` 失败。
- 扩展 smoke coverage，验证 duplicate submit inputs 不创建 run rows，duplicate annotation add inputs 不创建 annotation/revision rows，duplicate annotation edit inputs 不推进 `current_revision`。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Checkout Remove Duplicate Selector Rejection

已实现：

- 收紧 `exp checkout remove`：重复 `--token-id`、重复 `--path` 或混合 selector inputs 现在会按文档中的 exactly-one selector contract 以 `CONFIG_INVALID` 失败。
- 将 checkout-remove selector validation 移到 shared option occurrence counting，在 inspection lookup 或 filesystem trash staging 前执行。
- 扩展 inspection checkout smoke coverage，验证 duplicate remove selectors 会让 checkout path 保持存在、inspection path/token 保持 active，且不写 remove audit rows。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Experiment Token Duplicate Selector Rejection

已实现：

- 收紧 `exp token list|revoke|regenerate`：重复 selector options（`--token-id`、`--mode`、`--all`）现在会以 `CONFIG_INVALID` 失败，不再静默使用第一次出现的值。
- 将 guard 放在 token selection/mutation 之前，避免 revoke 和 regenerate 意外作用于比调用者请求更窄或更宽的 token set。
- 扩展 token lifecycle smoke coverage，验证 duplicate selectors 会保持 token rows、active token counts、restored token status 与 audit rows 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Prune And Secret GC Duplicate Selector Rejection

已实现：

- 收紧 `backup prune`：重复 `--keep` 或重复 `--older-than` 现在会在删除 backup files 前按 exactly-one selector contract 以 `CONFIG_INVALID` 失败。
- 收紧 `project secret gc`：重复 `--dry-run` 或重复 `--apply` 现在会在读取或删除 unreferenced secret rows 前以 `CONFIG_INVALID` 失败。
- 扩展 smoke coverage，验证 duplicate prune selectors 会保持 backup files 存在，duplicate secret GC selectors 会保持 orphan secret rows 与 audit counts 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Cache Prune Duplicate Selector Rejection

已实现：

- 收紧 `cache prune`：重复 selectors（`--all`、`--docker-images`、`--skydiscover-envs`、`--trash`、`--trash-all`）以及重复 `--older-than` 现在会以 `CONFIG_INVALID` 失败。
- 保持 duplicate selector rejection 发生在 cache row selection 与 path deletion 之前，包括 trash cache cleanup。
- 扩展 cache prune smoke coverage，验证 duplicate selectors 会保持 active trash cache rows 与 staged trash paths 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Catalog Duplicate Selector Rejection

已实现：

- 收紧 `catalog skydiscover add|update`：重复 `--origin-url`、`--ref` 或 `--commit` values 现在会以 `CONFIG_INVALID` 失败。
- 保持 duplicate selector rejection 发生在 clone/fetch/checkout 之前，也发生在 catalog row 或 audit writes 之前。
- 扩展 catalog lifecycle smoke coverage，验证 duplicate add selectors 不创建 local catalog contents、catalog rows 或 catalog audit rows，duplicate update selectors 会保持 pinned commit 与 update audit count 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Hard Remove Duplicate Confirmation Rejection

已实现：

- 为 actual hard-remove confirmation checks 增加共享 `require_force_confirm` 处理。
- 收紧 catalog/project/source/experiment/worktree/checkout/validation/run/artifact/log/annotation remove paths：重复 `--force` 或重复 `--confirm` values 现在会以 `CONFIG_INVALID` 失败，不再被 flag/first-value parsing 折叠。
- 扩展共享 confirm guard smoke helper，在既有 destructive lifecycle tests 中覆盖 duplicate force/confirm variants。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Config Duplicate Option Rejection

已实现：

- 增加共享 `require_options_at_most_once`，用于 single-value 或 single-use command options。
- 收紧 `project init`：重复 `--config`、config text overrides、source subdir/ref selectors 和 `--skip-baseline-test` 会在 source staging 或 project rows 写入前失败。
- 收紧 `project config show|export|import` 与 project config mutation surfaces：重复 `--version`、`--out`、`--config`、`--overwrite`、`--dry-run` 或 `--skip-baseline-test` 会以 `CONFIG_INVALID` 失败，不再静默使用第一个 option。
- 扩展 smoke coverage，验证 duplicate init/config options 会保持 project/config/audit rows 与 export files 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Observe Query Duplicate Option Rejection

已实现：

- 将 duplicate option rejection 扩展到 `run`、`submit`、pagination、numeric filters、boolean filters、time filters、complete-id option filters 和 sort parsing。
- 收紧 observe run/artifact/log list 与 export surfaces：重复 filter、sort、pagination、`--out`、`--overwrite` 和 include flags 会以 `CONFIG_INVALID` 失败，不再静默使用第一个 option。
- 扩展 smoke coverage，验证 duplicate run/submit options 不创建 runs，duplicate observe filters 渲染稳定 errors，duplicate export destinations 不创建 files。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_observe_list_pagination_contracts tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Collaboration Duplicate Option Rejection

已实现：

- 将 duplicate option rejection 扩展到 shared project-id parsing、source import limits、source subdir/ref helpers、experiment visibility options、context path commands、experiment checkout/restore paths、annotation target/list/show options 和 audit filters。
- 收紧 source import、experiment creation、annotation mutation/list/show、context show/repair、checkout creation 和 audit list/show：重复 single-value options 会以 `CONFIG_INVALID` 失败，不再被 first-value parsing 折叠。
- 扩展 smoke coverage，验证 duplicate collaboration/source/audit/context options 会保持 source/experiment/annotation/audit rows 与 checkout/export paths 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Key And Lifecycle Duplicate Option Rejection

已实现：

- 将 duplicate option rejection 扩展到 key management、project list/show 和 shared lifecycle reason parser。
- 收紧 key create/list/revoke、project list/show，以及 project/source/worktree remove reason parsing：重复 single-value options 会在写入前以 `CONFIG_INVALID` 失败。
- 扩展 smoke coverage，验证 duplicate key/project/lifecycle options 渲染稳定 errors，并在相关场景保持 credential、audit 与 lifecycle target rows 不变。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Lifecycle Remove Duplicate Flag Rejection

已实现：

- 扩展 destructive lifecycle smoke coverage，覆盖 project、source、validation、experiment、worktree、inspection checkout、run、artifact、log 与 annotation remove flows 中重复 `--dry-run` 和 `--cascade` options。
- 确认这些 duplicate flags 会在 mutation 前以 `CONFIG_INVALID` 失败，并在已覆盖路径中保持 rows、credentials、audit events 与 filesystem paths 不变。
- 保持 lifecycle flag behavior 与 CLI 其他位置使用的 shared single-value option parser 一致。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_observe_list_pagination_contracts tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Config Duplicate Option Rejection

已实现：

- 将 shared duplicate option rejection 扩展到 global `config reset --all` 和 `config validate --refresh-capabilities`。
- 收紧 config repair 与 validation surfaces：重复 boolean options 会在修改 config files 或探测 runtime capabilities 前以 `CONFIG_INVALID` 失败。
- 在既有 config reset/validate repair flow 中补充 duplicate global config flag 的 smoke coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Option Duplicate Coverage

已实现：

- 扩展 global option pre-scan smoke coverage，覆盖 duplicate `--home`、`--output`、`--key` 与重复 `--key-stdin`。
- 验证 duplicate global options 会在 command execution 前渲染稳定 `CONFIG_INVALID` errors，同时 standalone `--` 仍会停止 global parsing。
- 这次保持为 test-only golden coverage，因为 implementation 已经满足该 contract。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Key Stdin Input Contract Coverage

已实现：

- 扩展 global option pre-scan smoke coverage，覆盖 invalid `--key-stdin` input values。
- 验证 empty stdin、单独 newline、embedded newlines、NUL bytes 与额外 trailing newlines 会在 command execution 前以 `CONFIG_INVALID` 失败。
- 保持 standalone `--` stop-parsing behavior 的覆盖，确保 sentinel 之后看起来像 global options 的 command arguments 不会被预扫描处理。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Global Option Value Contract Coverage

已实现：

- 扩展 global option pre-scan smoke coverage，覆盖缺失 `--home`、`--output` 与 `--key` values。
- 添加明确的 `--output json` rejection coverage，验证 V1 按 CLI contract 仍只支持 `text` 与 `rich`。
- 验证这些 failures 会在 command handling 前渲染稳定 `CONFIG_INVALID` error blocks。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Nested Help Duplicate Option Rejection

已实现：

- 收紧 nested command help parsing：重复 `--all` 或 `--explain` 会以 `CONFIG_INVALID` 失败，不再被静默折叠。
- 保持 top-level `help` 与 nested `--help` 在 duplicate help options 上的行为一致。
- 扩展 smoke coverage，覆盖 top-level duplicate `--all` 和 nested duplicate `--explain`，同时保持既有 nested command help result schema。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Top-Level Help Option Error Coverage

已实现：

- 扩展 top-level `alab --help` smoke coverage，覆盖 invalid help options 与 duplicate `--explain`。
- 验证 `alab --help` 与 `alab help` 对 help option mistakes 渲染相同稳定的 `CONFIG_INVALID` error block shape。
- 保持既有 nested command help schema checks，同时扩展 help-option golden matrix。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Nested Help Flag Duplicate Rejection

已实现：

- 收紧 nested command help parsing：重复 `--help` 本身会以 `CONFIG_INVALID` 失败。
- 保持 nested command help requests 中 `--help`、`--all` 与 `--explain` 的 duplicate handling 一致。
- 扩展 smoke coverage，覆盖 `config show --help --help`，同时保持有效的 `config show --help` nested help output。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Trailing Global Option Coverage

已实现：

- 扩展 smoke coverage，覆盖 command path 之后提供的 global options，包括 `config show --home <path> --output rich`。
- 增加 trailing invalid `--output json` case，验证 post-command global parsing 仍会执行 V1 output enum 校验。
- 保留 standalone `--` coverage，证明 sentinel 之后看起来像 global options 的 arguments 仍保持 command-local。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Duplicate Option Helper Consolidation

已实现：

- 将 catalog SkyDiscover add/update、cache prune 与 experiment token selector 的 duplicate-option checks 收敛到 `require_options_at_most_once`。
- 移除这些 command families 中重复实现 shared single-value option rejection behavior 的本地 loops。
- 保持既有 error strings 不变，同时降低 catalog/cache/token surfaces 后续 CLI parser drift 的风险。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Optional Authorization Ambient Key Hardening

已实现：

- 收紧 optional-authorized helper paths，使 `ALAB_KEY` 不再提升 public、experiment-token 或 inspection-token command surfaces 的权限。
- 保留真正需要 admin/root credential 的命令通过 central `require_actor` path 使用 ambient `ALAB_KEY` 的能力。
- 增加 smoke coverage，验证 ambient admin keys 不会解锁 hidden-log reads、peer experiment tag mutation、admin-only private annotation targeting、mismatched inspection checkout removal，或绕过 context self-repair branch checks。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Fixed Positional Argument Count Hardening

已实现：

- 增加 shared fixed positional-count helper，用于 CLI grammar 要求固定 positional arguments 数量的命令。
- 收紧 global `config set`、project config/env/secret mutators 与 experiment tag add/remove，使额外 positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 增加 smoke coverage，验证这些 extra-argument failures 会保留 config versions、secret rows、audit counts、global config values 与 experiment tag rows。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Single Selector Argument Hardening

已实现：

- 增加 shared optional single-selector helper，在保留 existing missing-selector `*_NOT_FOUND` behavior 的同时，对 extra positional selectors 以 `CONFIG_INVALID` 拒绝。
- 收紧 key revoke、config reset、validation lifecycle、source lifecycle/show、experiment show/lifecycle/worktree/token/checkout/tag-list、observe run/artifact/log show/export/lifecycle、annotation edit/status/remove/show 与 audit show 的 selector parsing。
- 增加跨代表性 command families 的 smoke coverage，验证 extra selector arguments 会在 revoke credentials、change validation/source/tag/archive state、write export files、edit annotations 或 write audit rows 之前失败。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Init Mode Argument Hardening

已实现：

- 收紧 `project init` mode parsing，要求 exactly one positional mode，不再只接受第一个 mode 并静默忽略后续 positional arguments。
- 复用 shared fixed positional-count helper，使 missing、extra 与 invalid modes 继续保持相同的 `CONFIG_INVALID` user-facing contract。
- 增加 smoke coverage，验证 `project init local extra ...` 会在创建 project、source、config-version、validation、admin credential 或 add-audit rows 之前失败。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- Real SkyDiscover Python dependency-installation validation 仍是可选的 future environment hardening。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Real SkyDiscover Python Dependency Install Coverage

已实现：

- 增加 opt-in `real_skydiscover_python` pytest marker，并通过 `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1` gate real-environment test。
- 该测试在运行时构建本地 pure-Python wheel，通过真实 `uv` SkyDiscover evaluator environment 安装，在 evaluator 中 import，并验证 parsed reward/metrics。
- 同一测试验证 environment cache metadata 从 `built` 转为 `hit`，且不依赖 network access。
- 更新 README 与 test-spec documentation，记录新的 opt-in command 和 skip behavior。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Maintenance No-Positional Argument Hardening

已实现：

- 收紧 `project secret gc`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 收紧 `project locks clear-stale`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 增加 smoke coverage，验证这些 failure 会在任何 delete 或 clear operation 运行前保留 unreferenced secret rows、stale/live lock rows 与 audit counts。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Project Surface No-Positional Argument Hardening

已实现：

- 收紧 `project list`、`project show`、`project archive`、`project unarchive` 与 `status`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 root/admin project surfaces 既有 auth-first behavior，同时在 project lifecycle writes 前执行 documented option-only command grammar。
- 增加 smoke coverage，验证 extra positional archive/unarchive attempts 会保留 project status 与 audit counts，并验证 read-only project/status commands 拒绝相同 grammar drift。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-19 Auth And Global Config No-Positional Argument Hardening

已实现：

- 收紧 `auth init`、`auth root regenerate`、`config show` 与 `config validate`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 确保 `auth init extra` 会在创建 ALab home 前失败；`auth root regenerate extra` 会在 root authentication 后、revoking 或 creating root credentials 前失败。
- 增加 smoke coverage，验证 config read/validate no-positional failures 会渲染稳定 error blocks，并且不会继续进入 normal command path。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Key Surface No-Positional Argument Hardening

已实现：

- 收紧 `key create` 与 `key list`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 key-management surfaces 在 grammar rejection 前先做 credential checks，匹配 protected commands 既有 auth-first behavior。
- 增加 smoke coverage，验证 `key create extra ...` 会在添加 admin credentials 或 add-audit rows 前失败，并验证 root-scope 与 project-scope key list 都拒绝相同 grammar drift。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Catalog Surface No-Positional Argument Hardening

已实现：

- 收紧 `catalog skydiscover add|update|show|remove`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 root credential checks 与 remove confirmation checks 位于新的 grammar rejection 之前，同时仍确保在 clone/fetch/update/delete/database lifecycle work 前失败。
- 增加 catalog lifecycle smoke coverage，验证 extra positional add/update/remove attempts 会保留 catalog rows、pinned commits、local catalog contents 与 catalog audit counts。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Backup And Cache No-Positional Argument Hardening

已实现：

- 收紧 `backup prune` 与 `cache prune`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持既有 selector/missing/conflict validation priority，同时确保 extra positional arguments 会在 backup file deletion、trash path removal、cache row mutation 或 audit writes 前被拒绝。
- 增加 smoke coverage，验证 extra positional backup/cache prune attempts 会保留 backup files、active trash paths/rows 与 audit counts。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project Validate No-Positional Argument Hardening

已实现：

- 收紧 `project validate`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 protected project maintenance 既有 admin-auth-first behavior，同时确保 extra positional arguments 会在 validation row creation、baseline execution、project status mutation 或 active validation pointer changes 前被拒绝。
- 增加 smoke coverage，验证 `project validate extra --project <id>` 会保留 validation counts 与 project state，然后才执行真实 validation run。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project Config List/Import No-Positional Argument Hardening

已实现：

- 收紧 `project config show`、`project config export`、`project config import`、`project env list` 与 `project secret list`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 protected project config surfaces 的 auth-first behavior，同时确保 extra positional arguments 会在 config export writes、config import file reads、config version mutation 或 audit writes 前被拒绝。
- 扩展 smoke coverage，覆盖 no-positional read/list commands，以及会保留 output files、config version counts 与 audit counts 的 export/import failure paths。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Context Show/Repair No-Positional Argument Hardening

已实现：

- 收紧 `context show` 与 `context repair`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 duplicate `--path` 与 missing required `--path` validation priority，同时确保 extra positional arguments 会在可能进入 repair writes 的 context marker reads 前被拒绝。
- 增加 collaboration smoke coverage，验证 extra positional repair attempts 会保留 marker bytes 与 repair audit counts。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source List/Import No-Positional Argument Hardening

已实现：

- 收紧 `source list` 与 `source import`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持既有 source-origin 与 unsupported-selector validation priority，同时确保 extra positional arguments 会在 source-import temporary work directories、Git/source snapshot work、source row mutation 或 source add audit writes 前被拒绝。
- 增加 smoke coverage，验证 extra positional source import attempts 会保留 source row counts 与 source add audit counts，并验证 source list 拒绝相同 grammar drift。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Experiment Create/Search No-Positional Argument Hardening

已实现：

- 收紧 `exp create`、`exp list`、`exp search` 与 `exp best`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持既有 source selector conflict 与 unsupported `exp best --sort` validation priority，同时确保 extra positional arguments 会在 experiment row creation、worktree creation、token writes、path registry mutation 或 observe queries 前被拒绝。
- 增加 smoke coverage，验证 extra positional experiment create attempts 会保留 experiment counts 且不会创建 requested worktree，并验证 experiment list/search/best 拒绝相同 grammar drift。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Run And Submit No-Positional Argument Hardening

已实现：

- 收紧 top-level `run` 与 `submit`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 required message/body/ref validation priority，同时确保 extra positional arguments 会在 runner execution、final-run reuse/rerun、summary/feedback file reads、submission writes 或 experiment close mutation 前被拒绝。
- 增加 workflow smoke coverage，验证 extra positional run attempts 会保留 run counts，extra positional submit attempts 会保留 submission counts 并在 missing summary-file reads 前失败。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project And Checkout Remove No-Positional Argument Hardening

已实现：

- 收紧 `project remove` 与 `exp checkout remove`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 保持 duplicate selector/option validation priority，同时确保 extra positional arguments 会在 project whole-tree removal planning、trash staging、inspection checkout removal、token revocation、path registry mutation 或 remove audit writes 前被拒绝。
- 增加 smoke coverage，验证 extra positional remove attempts 会保留 project rows、project/control/worktree/inspection paths、inspection active path/token rows 与 remove audit counts。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Observe List No-Positional Argument Hardening

已实现：

- 收紧 `runs list`、`artifacts list` 与 `logs list`，使 extra positional arguments 以 `CONFIG_INVALID` 失败，而不是被静默忽略。
- 扩展 shared positional parser，使其识别更多带值 observe filter options，包括 `--stream`、`--size-min`、`--size-max` 与 `--truncated`，从而在更严格 grammar checks 下继续接受合法 filters。
- 增加 observe smoke coverage，验证 extra positional list attempts 会在 runs、artifacts 与 logs surfaces 渲染稳定 error blocks，并保持 duplicate-option validation priority。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project-Context Invalid Status Hardening

已实现：

- 收紧 marker-only project-context 下 invalid projects 的 `status`，使其使用与 explicit public `status --project <id>` 相同的安全 invalid-only output。
- 保持 valid public status shape 与 experiment/inspection token status detail，同时避免无 key invalid project contexts 渲染 task/config 内容。
- 增加 invalid marker-only project context status output 的 smoke coverage。

仍未完成：

- 完整 CLI golden matrix 仍有较小的 long-tail gaps，主要在 uncommon source/config combinations 与 selected destructive failure variants。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Lifecycle Unsupported-Option Hardening

已实现：

- 增加 shared known-option guard，覆盖 mutation-oriented lifecycle 与 credential surfaces，避免其他命令的 options 被 shared positional parser 静默跳过。
- 将该 guard 应用于 key revoke、project/source/experiment/validation lifecycle remove/archive/unarchive paths、worktree 与 inspection checkout lifecycle paths、observe record archive/unarchive/remove paths，以及 annotation archive/unarchive/remove paths。
- 增加 smoke coverage，验证 unsupported cross-command `--reason` inputs 会在 key revoke、source archive、log archive、experiment archive 或 project archive side effects 前以 `CONFIG_INVALID` 失败。

仍未完成：

- 部分 non-mutating read-only surfaces 仍依赖 command-specific duplicate/positional validation，而不是完整 per-command unknown-option matrix。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Read Selector Unsupported-Option Hardening

已实现：

- 将 shared known-option guard 扩展到 read-oriented selector/export surfaces，包括 source/experiment/run/artifact/log/annotation/audit show commands，以及 artifact/log exports。
- 同步覆盖 experiment token list selectors，避免 token listing 静默忽略 cross-command options。
- 增加 smoke coverage，验证 unsupported cross-command `--reason` inputs 会在 show/export reads 完成前或 export files 写入前以 `CONFIG_INVALID` 失败。

仍未完成：

- 部分 broad list surfaces 仍依赖 command-specific duplicate/positional validation，而不是完整 per-command unknown-option matrix。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 List Surface Unsupported-Option Hardening

已实现：

- 将 shared known-option guard 扩展到 broad list surfaces，包括 key、project、project env/secret、source、experiment query、experiment tag、observe run/artifact/log/annotation，以及 audit list commands。
- 保持 repeated `--tag` semantics 与既有 `exp best --sort` unsupported-sort error，同时更早拒绝 unrelated cross-command options。
- 增加 smoke coverage，验证 unsupported cross-command `--reason` inputs 会在代表性的 root、project、source、experiment query、observe list、annotation list 与 audit list surfaces 中以 `CONFIG_INVALID` 失败。

仍未完成：

- 完整 per-command unknown-option golden matrix 仍未穷尽每个 configuration 与 adapter command variant。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Key List Root Flag Positional Hardening

已实现：

- 增加 command-level positional value-option overrides，使命令可以区分在其他 surface 中是 value、但在本命令中是 flag 的共享 option names。
- 收紧 `key list --root`，避免 trailing positional arguments 因为 `--root` 在 artifact list surface 中是 value filter 而被静默跳过。
- 增加 smoke coverage，覆盖 `key list extra --root` 与 `key list --root extra` 两种拒绝路径。

仍未完成：

- 对所有 command contexts 中 shared option name 的完整 audit 仍在持续推进。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Run Submit Unsupported-Option Hardening

已实现：

- 为有副作用的 `run` 与 `submit` workflow commands 增加 known-option guards。
- 保持 submit 对 `--summary-stdin` 与 `--feedback-stdin` 的显式 unsupported messages，同时确保 unrelated cross-command options 会在 file reads、runner execution 或 submission writes 前被拒绝。
- 增加 smoke coverage，验证 unsupported `run --summary` 不会创建 run，unsupported `submit --path` 不会创建 submission。

仍未完成：

- 其他 command surfaces 仍需要同类 per-command unknown-option audit，尤其是 project config/env/secret mutation、init/import/create、context、cache 与 catalog commands。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Project Maintenance Unsupported-Option Hardening

已实现：

- 为 project config show/export/import/set、project env set/unset、project secret set/unset/gc、manual project validation 与 stale-lock clearing 增加 known-option guards。
- 保持既有 duplicate-option 与 positional validation messages，同时确保 unrelated cross-command options 会在 config file reads、config-version writes、stdin secret reads、validation runs、lock deletion 或 lifecycle audit writes 前被拒绝。
- 增加 smoke coverage，验证 unsupported `--reason` inputs 不会创建 config versions、secret rows、validations、lock-clear audit rows、config export files 或 import input files。

仍未完成：

- 其他 command surfaces 仍需要同类 per-command unknown-option audit，尤其是 init/import/create source surfaces、context、cache 与 catalog commands。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Context Cache Catalog Unsupported-Option Hardening

已实现：

- 为 SkyDiscover catalog add/update/show/remove、backup prune、cache prune、context show 与 context repair 增加 known-option guards。
- 保持既有 selector、duplicate-option、confirm 与 lifecycle reason validation，同时确保 unrelated cross-command options 会在 catalog Git operations、filesystem pruning、trash deletion、marker repair、path-registry mutation 或 audit writes 前被拒绝。
- 增加 smoke coverage，验证 unsupported options 会保持 catalog rows/audit counts pinned、backup 与 trash files present、cache rows active，以及 context marker/audit state unchanged。

仍未完成：

- 其他 command surfaces 仍需要同类 per-command unknown-option audit，尤其是 project init、source import、public experiment create source selectors、annotation add/edit，以及 experiment token/checkout edge selectors。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Source Create Unsupported-Option Hardening

已实现：

- 为 `project init`、`source import` 与 `exp create` 增加 known-option guards，覆盖 documented source selector、inheritance、mutable policy、visibility、tag 与 inline source limit options。
- 保持 `project init` 既有 runtime-flag rejection，以及 source import 对 `--source-ref`、`--from-exp`、`--from-commit` 等 invalid selectors 的 source-specific `SOURCE_INVALID` messages。
- 增加 smoke coverage，验证 unsupported `--reason` inputs 不会创建 project/source/config/validation/credential rows、source refs、experiment worktrees、source/experiment rows 或 add-audit events。

仍未完成：

- 其他 command surfaces 仍需要同类 per-command unknown-option audit，尤其是 annotation add/edit 与部分 experiment token/checkout edge selectors。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_project_init_rejects_runtime_flags tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Annotation Mutation Unsupported-Option Hardening

已实现：

- 为 `annotate add` 与 `annotate edit` 增加 known-option guards，覆盖 project targeting、target selectors、body inputs、author labels 与 private visibility selectors。
- 保持 V1 显式 `--body-stdin is not supported` message，同时确保 unrelated cross-command options 会在 body-file reads 或 annotation revision writes 前被拒绝。
- 审计当前 worktree 中的 experiment token 与 checkout selector handlers；这些 surfaces 已在前序增量中使用 known-option guards。
- 增加 smoke coverage，验证 annotation add/edit 上的 unsupported `--reason` inputs 不会读取缺失 body files，也不会创建 annotation rows 或 revisions。

仍未完成：

- CLI unknown-option audit 目前主要剩余 scattered edge aliases 与 future adapter-specific command variants，但完整 golden matrix 仍需要更广泛的枚举覆盖。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 Core Command Unsupported-Option Hardening

已实现：

- 为 `auth init`、`auth root regenerate`、`key create`、global `config show|set|reset|validate`、`project show`、`status` 与 experiment tag add/remove 增加 known-option guards。
- 保持既有 positional 与 duplicate-option errors，同时确保 unrelated cross-command options 会在 home creation、root key rotation、admin key creation、config rewrites、status maintenance、project rendering 或 tag mutation 前被拒绝。
- 保持 documented standalone `--` command-local sentinel behavior：known-option guards 会在 `--` 处停止扫描，所以后续 tokens 不会被解释为 command options。
- 增加 smoke coverage，验证 unsupported `--reason` inputs 不会创建 homes、rotate root keys、create admin credentials、rewrite global config values 或 mutate experiment tags。

仍未完成：

- strict CLI matrix 仍需要对所有 aliases 做更广泛的 generated 或 table-driven coverage，但最常用的 write/read surfaces 现在已有显式 known-option guards。
- 更广泛的 live SkyDiscover catalog 与 networked dependency validation 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_option_contract_edges tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`

## 2026-05-20 CLI Known-Option Registry Contract

已实现：

- 增加 registry-level CLI contract test，遍历每个 `registry.COMMANDS` handler，并要求每个非 help command 要么直接调用 `require_known_options`，要么委托给已加 guard 的 shared observe/annotation helpers。
- 断言 shared observe archive/unarchive/remove helpers 与 annotation status helper 保持自己的 known-option guard，因此 `runs archive`、`observe logs remove`、`annotate archive` 等 thin aliases 不需要重复 command-specific smoke flows 也会被覆盖。
- 增加 allowlist metadata checks，要求每个 `require_known_options` tuple 都必须是 literal、无重复项，并且只由 declared value options 或显式归类的 flag options 组成。
- 增加 registry alias 与 matcher contracts，要求 command paths 唯一、`COMMANDS_BY_PATH` 精确镜像、credential surface names 稳定、longest-match behavior 正确，并且 shared-handler aliases 的 object type/credential schema 一致。
- 增加 registry object-type contract，现在会解析 canonical `docs/spec_cli.md` primary object-type table；当未来新增命令缺少 `registry.COMMANDS` metadata、未在文档中列出且不共享 documented alias handler，或映射到错误 primary `object: <type>` 时会失败。
- 增加配套的 CLI spec synchronization contract，使用同一 parser 解析英文和中文 primary object-type tables；当 `docs/spec_cli.md` 与 `docs/spec_cli_cn.md` 的 command coverage 或 object-type mappings 出现漂移时会失败。
- 增加 docs-derived stable error-code exit mapping contract，解析英文和中文 CLI spec tables，并要求两份文档都与 `ERROR_EXIT_CODES` 一致，包括用文字限定的 `RUNNER_ERROR` exit `1` 语义。
- 增加 docs-derived success-field order contracts，覆盖低副作用 global repair commands（`auth init`、`config show`、`config set` 与 `config reset`）、project initialization/read commands（`project init`、`project show` 与 `project config show`）、source read commands（`source list` 与 `source show`）、credential key commands（`key create`、`key list --root`、`key list --project` 与 `key revoke`）、experiment/observe commands（`exp create`、`observe experiments list`、`observe experiments show`、`exp tag add`、`exp tag remove` 与 `exp tag list`）、local runner observe commands（`run`、`observe runs list` 与 `observe runs show`）以及 run-scoped observable asset commands（`observe artifacts list`、`observe artifacts show`、`observe logs list` 与 `observe logs show`），证明它们渲染出的 text field labels 与 canonical English CLI spec order 一致。
- 将 `project init` docs-derived contract 从已有 local-source path 扩展到 `empty` 与本地 `git` mode variants，证明二者共享 canonical init field order，并遵守 raw admin-key 只渲染一次且不重印 root key 的规则。
- 将同一个 `project init` mode-variant contract 继续扩展到 Harbor 与 SkyDiscover adapter init paths，使用本地 fixture refs 和 skipped baseline validation，证明 adapter-backed init 同样遵守 canonical init field order 以及 raw admin-key/root-key 渲染规则。
- 增加 docs-derived `auth root regenerate` success-field contract，并加入 raw-key safety assertions：revoked root key 不会再次渲染，replacement root key 只出现一次，且 retained `audit show` metadata 会记录 sanitized regenerate context 而不含 raw key material。
- 增加 `auth init`、`project init` 与 `key create` 的 raw credential secret-rule coverage，证明生成的 raw key 只在目标 success object 中出现一次，同时调用方 credential 和先前 admin key 保持隐藏；key revoke 现在也有 docs-derived `audit show` metadata contract，证明 sanitized revoked-credential context 被保留。
- 将 global `config validate` success fields 拆成明确的 `config` 与 `capability` object schemas，同步中文 CLI spec，并增加 docs-derived contract 证明两个 rendered blocks 都遵守文档字段顺序。
- 增加 docs-derived `project secret set`、`project secret list` 与 `project secret unset` success-field contracts，并断言 raw secret value 不会被渲染，同时 fingerprint 与 referenced status 保持可见。
- 增加 docs-derived `project secret gc` success-field contract，并使 renderer 对齐 CLI spec：输出 `dry run`、`deleted count`、repeated `secret value id` 和 `audit id`，且不再渲染 candidate secret names。
- 将 `project secret gc --apply` contract 延伸到 `audit show`，证明 retained sanitized metadata 只暴露 deletion count，不泄露 secret name 或 raw secret value。
- 拆分 CLI spec 中 `project env` success fields，将 `set|unset` mutation output 与 per-env `list` output 分开，并增加 docs-derived contract 证明 `project env set`、`project env list` 与 `project env unset` 遵守各自 schema。
- 将 docs-derived success-field contracts 扩展到 `project config export`、`project config import`、`project config set` 与 `project validate`，并增强 parser 以支持带 required options（例如 `--out`）的 command headings，以及 `project config set` 继承 `project config import` success schema 的情况。
- 明确 `project config export` secret rule：只写 retain marker 和 fingerprint，不写 raw secret value；并增加 docs-derived contract，证明 `project config show`/`export` 不会在 stdout 或 exported TOML 中暴露 raw secret value，同时保留 secret name、fingerprint 和 retain metadata。
- 使 CLI spec 中的 `project locks clear-stale` 与 audited lifecycle behavior 对齐，补充 `audit id` 字段，并增加 docs-derived contract 覆盖无 stale lock 输出和实际清理 stale lock 输出。
- 增加 docs-derived maintenance prune success-field contracts，覆盖 `backup prune` 与 `cache prune`，包括对带括号 required selectors 的 command heading parser 支持，以及 repeated pruned backup paths、selected cache kinds 和 audit ids 的覆盖。
- 将 CLI spec 中 audit show 的字段名明确为 `sanitized metadata`，同步中文 audit show schema 与英文 field order，并基于真实 backup-prune audit event 增加 docs-derived `audit list`/`audit show` success-field contracts。
- 将 source lifecycle CLI spec 拆成可机器校验的 `source import`、`source archive`、`source unarchive` 与 `source remove` 字段 schema，同步扩展后的中文 source section，并增加 docs-derived contracts 覆盖 empty/local/Git import origins、`SOURCE_EMPTY_AFTER_FILTER` 与 `TRACKED_SENSITIVE_SOURCE_FILE` warning output、archive/unarchive timestamps 及 retained `audit show` metadata、无 blocker dry-run removal、actual source removal 后 source row 被持久删除，以及 removed Git source refs 的 `audit show` metadata。
- 使用本地 Git upstream fixture 增加 docs-derived `catalog skydiscover add`、`catalog skydiscover show`、`catalog skydiscover update` 与 `catalog skydiscover remove` success-field contracts，覆盖 pinned commit changes 和 audited add/update/remove output，且不访问网络。
- 使 CLI spec 中 `project validation archive|unarchive` 与实际 `archived at`/`unarchived at` 和 `audit id` 字段对齐，明确 validation remove 的 repeated `blocker` label，并基于无依赖 validation row 增加 archive/unarchive `audit show` metadata、dry-run remove、actual remove 以及保留 deleted artifact/log 与 filesystem-target counts 的 `audit show` metadata docs-derived contracts。
- 将 experiment archive/unarchive CLI spec 拆成明确的 `archived at` 与 `unarchived at` schema，同步中文 spec，并基于真实 experiment worktree 增加 docs-derived `exp archive`/`exp unarchive` contract。
- 扩展 project lifecycle CLI spec，显式写出 project remove count fields 和 repeated `blocker`，同步中文 archive/unarchive timestamps，并增加 docs-derived `project archive`、`project unarchive` 以及 archived project 的 `project remove --dry-run --cascade` contracts，动态覆盖 repeated filesystem path/planned-trash labels。
- 为 project 与 experiment archive/unarchive lifecycle event 增加 retained audit metadata，记录 previous/resulting status 与 transition timestamp，并通过 `audit list` 和 `audit show` 解析真实事件的 docs-derived contracts 锁定。
- 扩展 experiment remove CLI spec，显式写出 deleted run/artifact/log/annotation count fields 和 repeated `blocker`，同步中文 schema，并增加 docs-derived archived experiment 的 `exp remove --dry-run --cascade` contract，动态覆盖 repeated filesystem path/planned-trash labels。
- 增加 docs-derived experiment worktree lifecycle contracts，覆盖 `exp worktree remove` dry-run/actual output 与 `exp worktree restore`，并验证 worktree remove/restore 的 retained `audit show` metadata 和 restore 的 raw-token 写入/不渲染规则；同时增加 `exp token list`、`exp token regenerate` 与 `exp token revoke` contracts，并断言 token list/regenerate/revoke 遵守 raw-token 不渲染规则，且 token regenerate/revoke 会保留 `audit show` metadata。
- 将 docs-derived `exp create` contract 扩展到同样的 raw-token 写入/不渲染断言，证明初始 worktree token creation 会写 `.alab/token`，但不会打印 raw token。
- 增加 docs-derived `exp create --source-ref` success-field 与 lineage contract，证明显式选择已有 source 会遵守 canonical output field order、复用 selected source 且不创建 inline source row、记录 source-origin metadata，并且 stdout 不暴露 raw worktree token。
- 增加 inline local、Git 与 empty source origins 的 docs-derived `exp create` success-field contracts，证明每种 `--source-*` bootstrap path 都遵守 canonical field order、创建 source-backed experiment、写入 token path，并且 stdout 不暴露 raw worktree token。
- 增加 docs-derived `exp create --from-exp` success-field 与 lineage contract，证明 from-experiment creation 遵守 canonical output field order、写入但不打印 child worktree token、复用 parent source 且不创建新 source row，并记录 `creation_origin.kind = from_exp` metadata。
- 增加 docs-derived inspection checkout contracts，覆盖 `exp checkout` 和 `exp checkout remove` dry-run/actual output，包括 conditional path/trash 字段，并严格断言 raw inspection token 写入/不渲染规则。
- 将 `exp checkout remove` contract 延伸到 `audit show`，证明 retained audit metadata 包含 token revocation/hash details，但不泄露 raw inspection token 或原始 checkout 绝对路径。
- 将 `exp checkout` create contract 延伸到 `audit show`，证明 retained add metadata 记录 inspection token id、pinned commit、path registry id 与 created-for path hash，但不泄露 raw inspection token 或 checkout path。
- 增加 docs-derived `submit` success-field contract，基于真实 reusable passed run 验证 accepted submission output 遵守 CLI spec 字段顺序，并保持 final run/commit、stored-summary flags、closed experiment status 与 repeated `ref` 渲染对齐。
- 明确 annotation remove CLI spec 将 blockers 渲染为 repeated `blocker` 字段，同步中文 schema，并增加 docs-derived annotation contracts，覆盖 `annotate add`、`annotate edit`、`observe annotations list|show --history`、`annotate archive`、`annotate unarchive`、archive/unarchive `audit show` metadata，以及 `annotate remove` 的 active-blocker/dry-run/actual output。
- 将 observe run/artifact/log CLI spec 拆成显式 `list|show|export`、`archive`、`unarchive` 与 `remove` success-field schemas，同步中文 observe summary，并把 docs-derived contracts 扩展到 run archive/unarchive，以及基于真实 captured files 的 artifact/log export 和 archive/unarchive output。
- 为 observe run/artifact/log archive 与 unarchive events 增加 retained audit metadata，并将 docs-derived run/artifact/log contracts 延伸到 `audit show`，验证 previous/resulting archive status 与 transition timestamps。
- 增加 docs-derived observe remove contracts，覆盖 artifact/log active-blocker dry-runs、archived dry-runs 和 actual removals，以及 dependent logs archived 后的 run `--cascade` dry-run/actual removal，并动态验证 repeated filesystem path 与 planned trash move labels。
- 将这些 observe remove contracts 延伸到 `audit show`，证明 actual artifact/log/run removals 会保留 sanitized filesystem target metadata，以及 run dependent/latest/final-run metadata。
- 将 docs-derived read/diagnostic contracts 扩展到 `project list`、`context show` 与 `context repair`，把 project inventory 和 marker repair output 绑定到 canonical CLI spec field order。
- 将 `context repair` contract 延伸到 `audit list` 和 `audit show`，证明 retained repair metadata 记录 repair mode、registry id、old/new path hashes、row-creation status 与 timestamp，但不泄露 raw paths 或 credentials。
- 将 docs-derived experiment observe contract 从 list/show 扩展到 `observe experiments search` 和 `observe experiments best`，使用真实 passed run 确保 best output 非空且遵守共享 experiment result schema。
- 修正 CLI spec primary object-type table，在英文和中文文档中都显式列出 `project init` 会生成 `project` result object。
- 增加 all-commands help schema contract，证明 `help --all --explain` 会用稳定的 `help` 与 `help_command` field ordering、registry-backed summaries 精确覆盖每个 registered command 一次。
- 增加 runtime preflight matrix，证明每个 non-global-public registered command 在没有 context/key/home 时都会以 `COMMAND_UNAVAILABLE` 失败、输出稳定 error schema，且不会创建 `ALAB_HOME`。
- 使用 handler-level argument payloads 扩展 locked-command preflight matrix，包括 unsupported options、`--value-file`、`--body-file`、submit summary/feedback files、`--config`、`--out`，以及 parent directory 缺失的 `--out`，证明 unavailable commands 仍会在 command-specific parsing、file reads、file writes、output-parent creation 或 home creation 前失败。
- 增加匹配的 nested-help payload matrix，证明 selected `--help --explain` requests 在存在 handler-level payload arguments 时也使用同一个 locked capability decision，同时仍避免 file reads、output writes、output-parent creation 与 home creation。
- 增加 runtime nested-help 与 top-level all-help matrices，证明每个非 `help` registered command 都能渲染 selected `--help` 和 `--help --explain` output，并保持稳定 field ordering、registry-backed summaries、no-context availability values、locked reasons、unlock hints、capability sources，且不会创建 `ALAB_HOME`。
- 通过实际 CLI entrypoint 覆盖 `help --all --explain` 和 `--help --all --explain`，确保所有 registered commands 都精确出现一次，并使用与 selected nested help 相同的 no-context availability contract。
- 增加 default-help runtime coverage，覆盖 no-command `alab`、`alab help` 与 `alab --help`，证明 locked commands 会被隐藏、global-public rows 保持 registry order、field ordering 稳定，且 help display 不会创建 `ALAB_HOME`。
- 将 central help-schema contract 提升为直接从 `docs/spec_cli.md` 解析 `help` 与 `help_command` 字段顺序，防止未来 CLI spec edits 与 top-level/default help rendering 漂移。
- 增加 capability-surface registry contracts，确保 resolver path sets 不会引用未注册命令，global public commands 保持 unauthenticated，observe read/lifecycle commands 保持 token-or-admin，且 status/run/submit/public experiment creation 保持预期 credential surfaces。
- 增加 runtime read-alias equivalence contract，证明 `exp`/`observe experiments`、`runs`/`observe runs`、`artifacts`/`observe artifacts`、`logs`/`observe logs` 和 `annotations`/`observe annotations` 的 read/export aliases 在同一组 saved project data 上渲染完全一致的 structured stdout。
- 增加 `runs`、`artifacts` 与 `logs` top-level archive/unarchive/remove aliases 的 runtime lifecycle-alias coverage，证明 remove dry-runs 与 canonical `observe ... remove` 形式 byte-identical，archive/unarchive aliases 按 canonical docs-derived field order 渲染。
- 在 CLI contract suite 中增加 strict text-renderer contract，锁定 object-block 分隔、primary results 后的 warning blocks、repeated list labels、nullable `none`、literal user text `none`，以及 empty multiline `[empty]` rendering。
- 增加 CLI-level `--output rich` contract，证明 prefix 和 trailing global placement 会渲染与 text output 相同的 result data，不会把 `rich` 持久化到 global config，并且 persisted `output.format = "rich"` 仍会被拒绝。
- 增加 CLI-level `--key-stdin` validation matrix，证明 empty input、单独 newline、embedded newlines、NUL bytes、额外 trailing newlines、重复 `--key-stdin`，以及两种 `--key`/`--key-stdin` 顺序都会以稳定 `CONFIG_INVALID` 失败，同时单个 trailing newline 会在有效 root authentication 前被剥离。
- 增加 root/admin not-found contract，证明 run、validation、artifact、log、annotation、credential、audit 与缺失 SkyDiscover catalog selectors 会渲染精确的 object-specific `*_NOT_FOUND` error blocks 且 exit `2`，同时保留 documented `CACHE_NOT_FOUND` mapping 为 exit `2`。
- 增加 CLI-level complete-id contract，证明 project、source、experiment、validation、run、artifact、log、annotation、credential 与 audit 的缩写 ALab object selectors 会以稳定 `CONFIG_INVALID`/`object ids must be complete` output 失败，而不会被当作 object-specific lookup。
- 增加 CLI-level RFC 3339 time-filter matrix，覆盖 audit、experiment、run、artifact、log 与 annotation filters，证明 missing offsets 和 malformed timestamp shapes 会以稳定 `CONFIG_INVALID` 失败，同时 numeric offsets 可被接受。
- 增加 CLI-level debug-mode contract，证明 internal system failures 只会在 `ALAB_DEBUG=1` 下打印 traceback，normal mode 只保留稳定 error block，debug traceback 不暴露 local/env secret sentinel values，并且普通 `CONFIG_INVALID` failures 即使在 debug mode 下也不会输出 traceback。
- 增加 docs-derived error-exit mapping contract，对比英文与中文 CLI specs 和 implementation table，通过 runtime lookup 验证每个 documented code，并强制 V1 规则：未来 `*_NOT_FOUND` codes 默认 exit `2`，未知 internal codes 默认 exit `5`。
- 增加 CLI-level `HOME_EXISTS`/`OUTPUT_EXISTS` contract，覆盖 initialized home、non-empty unrelated home，以及 config/artifact/log export targets，证明稳定 error blocks、existing output bytes 不被改写，并且 `--overwrite` recovery paths 成功。
- 增加 reusable storage JSON contract validator，覆盖 persisted JSON objects 的 schema version、required keys、unknown keys 与 non-object rejection。
- 将 JSON contract validator 应用于 runtime capability details 与 SkyDiscover catalog metadata 读取，并把 stored SkyDiscover catalog metadata 对齐到文档中的 safe key set（`safe_summary`、`task_refs`、`evaluator_refs` 和 `warnings`）。
- 将 generated cache entry metadata 对齐到 documented safe cache JSON contract：`metadata_json` 只保存 `safe_summary`、`inputs_hash` 和 `warnings`，Docker tags 与 Python environment paths 保留在专用列，并在 cache hits 时清理 legacy cross-column values。
- 将 credential metadata reads/writes 对齐到 documented safe credential JSON contract，包括 default admin/token metadata 生成、credential verification 成功后的 unknown-key rejection，以及 inspection checkout self-repair 依赖 marker-pinned commit，不再把 `inspection_commit` 写入 credential metadata。
- 将 source origin metadata reads/writes 对齐到 documented safe origin JSON contract，增加 per-origin `origin_id`，强制 primary-origin/origins consistency，并在 source display 或 dedupe metadata update 前拒绝 unknown origin keys。
- 将 annotation target 与 visibility JSON reads/writes 对齐到 documented annotation JSON contracts，包括 fixed-key target payloads、path/line target shape checks、private visibility creator requirements，以及 project-visible rows 不再持久化 null `creator_exp_id`。
- 将 experiment metadata reads/writes 对齐到 documented experiment metadata JSON contract，包括 source、inline-source 与 from-experiment creation 的 fixed creation-origin variants、display safe-summary validation，以及 experiment list/search/sort/result rendering 中的 validated metadata use。
- 将 experiment policy reads/writes 对齐到 documented experiment policy JSON contract，包括 optional mutable overrides、normalized visibility experiment-id storage，以及 mutable-scope checks 和 token/public visibility calculations 中的 validated policy use。
- 将 run 与 validation record reads/writes 对齐到 documented execution record JSON contract，包括 config hash recording、finite numeric metrics、warning arrays、sanitized stale-interruption metadata、sanitized mutable-scope diagnostics，以及 validated observe run filtering/rendering。
- 将 audit deleted-id 与 metadata writes 以及 audit show rendering 对齐 documented audit JSON contracts，包括 normalized deleted-id count/id maps、fixed safe audit metadata keys，以及面向 future audit metadata additions 的 strict top-level unknown-key rejection。
- 将 final submission refs writes 对齐 documented submission refs JSON contract，在保留 first-seen ref order 的同时强制 single-`none` form 或 deduplicated complete experiment id refs。
- 将 stored project config reads/writes 对齐 documented `project_config_versions.canonical_config_json` contract，包括 `git` section、strict top-level keys、stored secret marker object shape，以及 imported secret markers 的 canonical fingerprint retention。
- 增加 fail-closed `.alab/context.json` marker contract validation，覆盖 detection、repair、marker writing 和 token regeneration，强制 marker version、known keys、context-specific ids、project repo hashes、inspection commits 与 optional repair timestamps。
- 为每个 registered non-help command 增加 generated runtime unknown-option matrix，按需使用 explicit root/admin credentials 或 experiment worktree token，并断言 `CONFIG_INVALID` unsupported-option failures 不改变完整 SQLite snapshot、global config、context markers 或 worktree token files。
- 增加 global-option placement contract，证明 `--home`/`--key` 在 command path 前后都可用，包括 top-level observe aliases，同时 standalone `--` 会在后续 global-looking tokens 前停止 global pre-scan。
- 锁定 `--all` help ordering，确保 available commands 会先于 locked commands 渲染，同时每组内部保持 registry order。
- 增加 global-public unsupported-option runtime matrix，覆盖 `help`、`--help`、`auth init`、global config repair/diagnostic commands 与 context diagnostics/repair，证明 unsupported command options 会在任何 `ALAB_HOME` directory 创建前以稳定 `CONFIG_INVALID` output 失败。
- 增加 ambient-key help/capability runtime matrix，证明有效 `ALAB_KEY` 不会扩大 no-command help、`help`、`--help`、top-level `--all --explain` 或 selected nested help output；同一个 selected command 在 ambient credentials 下仍保持 locked，但使用显式 `--key` 会变为 available，并且 help rendering 期间仍不会触碰 handler payload files。
- 增加 explicit-root help/capability runtime matrix，覆盖 `--key` 与 `--key-stdin`，证明 root credential display 会遵循 registry credential classes、在没有 experiment worktree context 时保持 token-only commands locked、保持稳定 command ordering，并渲染 `explicit-root`/`root` credential metadata。
- 增加 explicit-admin help/capability runtime matrix，覆盖 `--key` 与 `--key-stdin`，证明 project admin display 会遵循 registry credential classes、保持 root-only 与 token-only commands locked、保持稳定 command ordering，并渲染 `explicit-admin`/`admin` credential metadata。
- 收紧 project admin keys 的 capability preflight，使带有不匹配显式 `--project` 的 selected help 与 direct execution 都会在 handler authentication 前以 `COMMAND_UNAVAILABLE` locked，而 same-project selected help 仍以 `project-admin` capability source 保持 available。
- 增加 project-context help/capability runtime matrix，证明 public project contexts 默认只暴露 global-public 与 public project commands，在 `--all --explain` 下渲染安全 locked rows，并且当项目目录中提供显式 key 时会切换到匹配的 admin/root command surfaces 与稳定 credential metadata。
- 增加 experiment-context help/capability runtime matrix，证明 worktree-token help 默认会暴露 global-public、public project experiment creation 与 experiment/observe token commands，在 `--all --explain` 下渲染安全 locked rows，保持 selected public `exp create` help 无 side effect，并且当 experiment worktree 中提供显式 key 时会切换到 admin/root surfaces，同时 `run`/`submit` 仍来自 `worktree-token` capability source。
- 收紧 experiment contexts 中 explicit admin/root 的 capability source rendering，使 token-only `run` 与 `submit` rows 在由有效 worktree token 提供可用性时报告 `worktree-token`。
- 增加 inspection-context help/capability runtime matrix，证明 inspection-token help 默认只暴露 global-public、visible observe read/export commands、status 与 inspection checkout removal；selected/direct `submit` 会在 handler file reads 前保持 locked，并且显式 admin/root keys 会切换到 project admin/root surfaces，同时 token-only `run`/`submit` 在 inspection checkouts 中仍不可用。
- 增加 explicit-key context-conflict runtime matrix，覆盖 `--key` 与 `--key-stdin`，证明 experiment 与 inspection contexts 中的 admin/root keys 不能使用不匹配的显式 `--project`；selected help 会渲染安全 conflict reason/source，direct execution 会以 `CONTEXT_CONFLICT` 失败，并且不会创建 handler output files。
- 增加 context-local `--key-stdin` equivalence matrix，证明 project、experiment 与 inspection help/capability output 在同一个 admin/root credential 下与 `--key` byte-for-byte 一致，覆盖 default help、`help --all --explain` 与 `--help --all --explain`。
- 增加 context-local read-command `--key-stdin` equivalence matrix，证明 side-effect-free project reads（`project show` 与 `project config show`，包含有/无显式 `--project`）在 project、experiment 与 inspection contexts 中对 admin/root credentials 都会生成与 `--key` byte-identical 的 output。
- 将 `status` CLI spec 拆成 project/public、experiment/inspection 和 public-invalid 字段 schema，并扩展 runtime coverage，证明每个 context 都渲染正确 object type 与 docs-derived field order。
- 增加 known-option coverage contract，证明 guarded service functions 内部每个 literal option read，以及 project selection、lifecycle reason、force confirmation、secret input、annotation body/privacy selectors 等 shared helper 的 option reads，都出现在该函数的 `require_known_options` allowlist 中。
- 增加 docs-derived command-option acceptance contract，从 `docs/spec_cli.md` 解析 canonical command syntax 和明确 option-contract lines，并要求每个 documented command option 都能被 registered handler 或 guarded helper 接受，同时不会把其他命令的说明性引用误当作当前命令选项。
- 将 documented command-option acceptance contract 扩展到 `docs/spec_cli_cn.md`，包含中文全角冒号的 contract-line prefixes，因此中文文档单独声明的 option 若未被 registered handler surface 接受也会失败。
- 将中文 CLI spec 中 global config、validation remove、experiment create/remove/checkout/worktree/token 和 annotation mutation surfaces 的机器可读 command headings 与 option-contract lines 同步到英文 CLI spec，并增加直接的 English/Chinese documented-option equivalence contract。
- 扩展 CLI spec command-surface parser，使其组合机器可读 command headings、primary object-table paths 与 registered command mentions，并增加直接的 English/Chinese surface coverage contract，要求两份 CLI specs 都精确覆盖 registered command paths。
- 将 docs-derived success-field parser 泛化为可读取任意 CLI spec，同步中文 spec 中 help/auth/config/config-validate/key/context/project/env/secret/source/catalog/experiment/token/tag/run/submit/observe/annotation/status surfaces 的 selected success-field lines，包含 object/scope variants，并增加 selected English/Chinese success-field equivalence contract。
- 将 representative root/admin object-specific not-found matrix 扩展到 project、source 与 experiment selectors，并继续覆盖 run、validation、artifact、log、annotation、credential、audit 和 catalog selectors；现在还断言每个 not-found failure 都保持完整 SQLite snapshot 和 global config 不变。Representative incomplete-object-id selector matrix 现在也加入相同的 no-DB/no-config-side-effect 断言。
- 扩展 CLI-level RFC 3339 invalid-time-filter matrix 与 representative `HOME_EXISTS`/export error matrix，断言 initialized home、invalid time filters、existing export targets 与 artifact/log export parent 缺失等 rejected inputs 不会改变 SQLite snapshot 或 global config；非 ALab 非空 home 也保持不被触碰，existing export targets 的 output-file bytes 保持不变，missing export-parent failures 不会创建 parent directories 或 output files。
- 将剩余 unsupported-option hardening 从 manual audit 转为 future command additions 会默认执行的 repeatable default-suite check。
- 为每个使用 `require_force_confirm` 的 hard-remove command 增加 generated force-confirm guard matrix，证明缺少 `--force`、缺少 `--confirm` 和 confirm 值不匹配都会以稳定 `CONFIG_INVALID` 失败，同时保持 SQLite rows、marker files、token files 和 removal target paths 不变。
- 为支持 dry-run 的 hard-remove commands 增加 generated dry-run no-write matrix，覆盖 project、validation、source、experiment、worktree、inspection checkout、run、artifact、log 与 annotation removal；每个 dry-run 都断言 `dry run: true`、`removed: false`、`audit id: none`，并保持完整 SQLite snapshot、marker/token files、removal target paths 与 home trash tree 不变。
- 为 active project、validation、source、experiment、run、artifact、log 与 annotation targets 的 actual forced hard-remove attempts 增加 generated lifecycle-blocker no-write matrix，证明 `RESOURCE_BUSY` blockers 会在任何 staging 或 mutation 运行前保持完整 SQLite snapshot、marker/token files、removal target paths 与 home trash tree 不变。
- 为目标已 archive 后的 actual forced validation、source 与 run removals 增加 generated dependency-blocker no-write matrix，覆盖 `dependent_records_require_cascade` 与 `dependent_records_not_archived`；该矩阵会保持完整 SQLite snapshot、marker/token files、target paths、project tree、home trash tree 与 source Git ref commit 不变。
- 执行 lifecycle spec 中 mutually exclusive hard-remove mode contract：支持 dry-run 的 hard-remove commands 现在会拒绝 `--dry-run` 与 `--force`/`--confirm` 混用，并增加 generated no-side-effect matrix，证明混合 planning/destructive modes 会在 DB、marker/token、path、project tree 或 trash 变化前以 `CONFIG_INVALID` 失败。
- 将 CLI specs 同步到 lifecycle remove-mode conflict rule，并增加 static service contract，要求所有同时接受 `--dry-run` 且调用 `require_force_confirm` 的 handler/helper 都必须调用 mixed-mode guard。
- 增加 docs-derived mixed-mode conflict declaration contract，扫描两份 CLI specs 中每个 documented `(--dry-run|--force --confirm ...)` remove surface，并要求对应 `Conflicts` 行明确包含 `--dry-run`、`--force` 和 `--confirm`。
- 增加 docs-derived English/Chinese conflict-option synchronization contract，并同步中文 CLI spec 中 config export/import/set、cache prune、experiment token selectors 与 submit refs 的 conflict lines。
- 增加 docs-derived stable error-code catalog 与 numeric exit-code table contract，证明英文/中文 error-code list、exit mapping table、numeric exit categories 与 implementation constants 保持同步。
- 增加 docs-derived warning-code catalog contract，在 CLI/runner/test specs 中记录已实现的 `DOCKER_SETUP_OUTPUT_CAPTURED` Docker setup-output warning，并要求每个已实现 stable warning code 都列入两份 CLI specs。
- 实现 V1 `.alab/token` permission warning path：当 token file 权限宽于 `0600` 时，token-context command output 会在 primary result 后追加 `TOKEN_FILE_PERMISSIONS`，且不重写用户的 file permissions。
- 增加 CLI token-write contract，覆盖 experiment creation、inspection checkout、worktree restore 和 token regeneration，证明 raw token files 以 `0600` permissions 写入且 `.alab/` Git exclude rules 存在；token regeneration 现在会在该 rule 被移除后重新刷新。
- 为每个 registered command 和 alias 增加 generated runtime global-option pre-scan error matrix，证明 duplicate global options、missing global values、invalid `--output` values，以及 `--key`/`--key-stdin` conflicts 会在 home creation、command matching、credential verification 或 handler execution 前以稳定 `CONFIG_INVALID` output 失败。
- 为每个 registered non-help command 和 alias 增加 generated runtime trailing-global placement matrix，证明 trailing `--home`、`--key` 与 `--output text` 会在 handler unsupported-option validation 前由 global pre-scan 消费，并保持 SQLite rows、global config、context markers 与 worktree token files 不变。
- 为每个 registered non-help command 和 alias 增加 generated runtime standalone-separator matrix，证明 `--` 后看起来像 global options 的 tokens 不会被 global pre-scan 消费，不会读取 `--key-stdin`，不会切换选中的 home，并保持 SQLite rows、global config、context markers、token files、source/catalog trees、export targets 与 would-be worktrees 不变。
- 增加 generated runtime explicit-credential unavailable-command matrix，覆盖 `--key` 和 `--key-stdin`，证明 root credentials 在 experiment worktree context 外不能运行 token-only commands，admin credentials 不能运行 root-only 或 token-only commands，并且都会在 handler option parsing、读取缺失 payload files、output writes、output-parent creation、SQLite mutation、global config/context marker/token mutation、Git operations、runner execution 或 filesystem staging 前失败。
- 增加 generated runtime project-context unavailable-command matrix，证明每个不属于 public project surface 的 registered command 都会在 handler option parsing、读取缺失 payload files、output writes、output-parent creation、SQLite mutation、global config/context marker/token mutation、Git operations、runner execution 或 filesystem staging 前以稳定 `COMMAND_UNAVAILABLE` output 失败。
- 增加 generated runtime experiment-context unavailable-command matrix，证明每个不属于 worktree-token surface 的 registered command 都会在 handler option parsing、读取缺失 payload files、output writes、output-parent creation、SQLite mutation、global config/context marker/token mutation、Git operations、runner execution 或 filesystem staging 前以稳定 `COMMAND_UNAVAILABLE` output 失败。
- 增加 generated runtime inspection-context unavailable-command matrix，证明每个不属于 inspection-token surface 的 registered command 都会在 handler option parsing、读取缺失 payload files、output writes、output-parent creation、SQLite mutation、global config/context marker/token mutation、Git operations、runner execution 或 filesystem staging 前以稳定 `COMMAND_UNAVAILABLE` output 失败。
- 加强 command-local duplicate option validation，覆盖 source/project initialization paths、project secret input、secret GC、experiment creation/best/token selectors、submit stdin flags、log hidden access 以及 annotation body/target/privacy inputs，使 singleton options 在 writes、file exports、runner execution 或 lifecycle audit rows 前失败。
- 增加 static singleton-option contract，要求每个 known command option 要么有 duplicate guard，要么明确分类为 repeated option；未来新增命令如果加入未分类 singleton option，default suite 会失败。
- 增加 runtime coverage，证明 `logs show --include-hidden --include-hidden` 会在 log lookup side effects 前以 `CONFIG_INVALID` 失败，并保持 SQLite 与 global config 不变。
- 增加 representative runtime singleton-duplicate matrix，覆盖 project init、source import、experiment create/best/token selectors、project secret set/GC、submit stdin flags、logs show 以及 annotation add/edit，证明重复 singleton options 会在 DB/config/marker/token 变化或读取缺失 body/value/config 文件前以稳定 `CONFIG_INVALID` 失败。
- 为每个 registered command-local singleton option 增加 generated runtime duplicate-option matrix，包括 helper-backed observe lifecycle 与 annotation status aliases，证明 duplicates 会在 availability fallback、selector lookup、file reads、DB/config/marker/token writes、filesystem staging、runner execution 或 lifecycle audit rows 前以稳定 `CONFIG_INVALID` 失败；lifecycle remove `--reason` guards 现在会在 project/selector lookup 前运行。
- 增加 generated registered-command success-field documentation contracts：每个 registered command 现在都必须能直接、通过 object/scope variants，或通过 canonical alias handler 解析到已记录的 CLI success fields，且解析出的 English/Chinese field contracts 必须保持同步。
- 修复中文 CLI spec 中 `project config set` 的契约说明，明确它继承 `project config import` 的 success/exit contract，而不是只依赖 prose。
- 收紧需要 value 的 option parsing：global 与 command-local options 在下一个 token 是另一个 `--...` option 时也会按 missing value 拒绝；并增加 representative no-side-effect runtime coverage，覆盖 global parsing、config export、source import、experiment creation/tags/tokens、log export、annotation targets、submit file inputs 和 SkyDiscover catalog add。
- 为每个 registered command-local value option 增加 generated runtime missing-value matrix，证明 absent option values 会在 availability fallback、mutually exclusive relationship validation、file reads、DB/config/marker/token writes、filesystem staging、runner execution 或 lifecycle audit rows 前以稳定 `CONFIG_INVALID` 失败；public `status --project` preflight 现在会报告 malformed missing value，而不是落到 `COMMAND_UNAVAILABLE`。
- 收紧 project config/env/secret mutation preflight，使 `--dry-run` 与 `--skip-baseline-test` 的组合会在读取 config 或 secret payload files、validation writes、SQLite mutation、context marker mutation 或 runner execution 前失败，并增加 runtime no-side-effect matrix，覆盖 config import/set、env set/unset 和 secret set/unset。
- 增加 runtime documented non-remove conflict matrix，覆盖 key root/project scope、SkyDiscover ref/commit selectors、backup/cache prune selectors、source import/show selectors、experiment source/from-exp selectors、experiment token selectors、submit refs 以及 annotation body/target selectors，证明稳定 `CONFIG_INVALID`/`SOURCE_INVALID` errors 不会产生 SQLite、global config、marker/token、source/cache tree、worktree 或 missing payload-file side effects。
- 扩展 opt-in real Docker suite，为 Harbor separate verifier 增加 `[verifier].image` 与 `tests/Dockerfile` 两条真实执行覆盖，证明 real containers 会报告 `verifier mode: separate`、解析 Harbor rewards、保留 hidden verifier stdout，并记录 Harbor Dockerfile image-cache metadata，同时 default suite 不依赖 Docker。
- 扩展 default fake-Docker Harbor runner suite，增加 separate verifier image execution 和 separate `tests/Dockerfile` build/cache coverage，证明 `verifier_mode = separate`、visible summary rendering、hidden stdout capture/redaction、Harbor env injection、network mapping、bundle mounts 与 Dockerfile cache metadata，且 default suite 不需要 Docker。
- 扩展 static CLI option audit，将 literal `command_args(...)` reads 纳入 known-option coverage，并增加 value-option registry contract，要求每个 literal `command_arg(...)` 或 `command_args(...)` read 都登记到 positional parsing 与 missing-value validation 使用的 registry 中。
- 增加 registered-command positional grammar contract，要求每个非 help command handler 都直接或通过已记录的 lifecycle helper path，使用共享 fixed-count 或 optional-selector helper 校验 positional arguments。
- 将同一 static option-read audit 扩展到 pagination、sorting、source selection、visibility/mutable policy overrides、credential selectors、typed filters 和 time filters 的 helper-mediated literal reads，避免未来 handler 通过 helper 读取未在 known-option allowlist 和 value-option registry 中声明的 option。
- 将 singleton duplicate-option audit 扩展到 helper-mediated source limit value parsing，使未来 source-limit handlers 能从 shared parser classification 继承 duplicate-guard coverage。
- 为每个 registered zero-positional command 增加 generated runtime extra-positional matrix，证明多余 positional arguments 会以稳定 `CONFIG_INVALID` 失败，并保持 SQLite rows、global config、context markers、token files、source/cache/project worktrees、export targets 与 would-be experiment worktrees 不变。
- 为每个 registered single-selector command 增加 generated runtime extra-positional matrix，包括 helper-backed observe 与 annotation lifecycle aliases，证明多余 positional arguments 会在 selector lookup、file export、token/path mutation、lifecycle audit writes 或 filesystem staging 前失败。
- 为每个 registered required single-selector command 增加 generated runtime missing-selector matrix，证明缺失 object selector 会在 SQLite mutation、global config 或 marker/token changes、file exports、inspection checkout creation、source/cache tree changes 或 lifecycle audit rows 前以稳定 object-specific `*_NOT_FOUND` errors 失败。
- 为每个 registered fixed-count positional command 增加 generated runtime extra-positional matrix，证明多余 positional arguments 会在 global config writes、project/source initialization、secret file reads、project config-version writes、experiment tag mutation 或 audit writes 前失败。
- 为每个 registered fixed-count positional command 增加 generated runtime missing-positional matrix，证明缺失 required positional arguments 会在 global config writes、project/source initialization、secret file reads、project config-version writes、experiment tag mutation 或 audit writes 前以稳定 `CONFIG_INVALID` 失败。
- 收紧 `project init`、`source import` 和 `exp create` 的 source-limit parsing，使 malformed `--max-files`、`--max-total-bytes` 和 `--max-file-bytes` values 会在 source staging 或 project/source/config/admin credential writes 前失败；`project init` 现在会在写入 project rows 前，对 staged initial source 执行同一 source-limit ceiling。
- 为使用共享 pagination、source-limit、integer、numeric 和 boolean parsers 的 registered commands 增加 generated runtime typed-value matrix，证明 malformed values 会以稳定 `CONFIG_INVALID` 失败，且没有 SQLite、config、marker/token、source/tree、export 或 worktree side effects。
- 将 generated typed/structured-value matrix 扩展到 sort fields、choice filters 和 RFC 3339 time filters，证明 malformed `--sort`、choice-style `--status` 以及 helper-mediated time-filter values 会以稳定 `CONFIG_INVALID` 失败，且不会产生 state changes。
- 将同一矩阵扩展到 `backup prune` 和 `cache prune` 的 retention count/day parsing，包括 `--keep` 和 `--older-than`，使 malformed retention values 会在 backup deletion、cache pruning 或 audit writes 前失败。
- 将 generated typed/structured-value matrix 扩展到 option-based ALab object id filters，包括 experiment source filters、token selectors、observe exp/run/validation filters 和 audit actor filters；annotation creation 现在会在 body-file reads 或 body storage 前校验 target ids 与 `--private-to-exp` ids。
- 收紧 annotation list filters，使 object-backed `--target-id`/`--target` values 和 `--created-by` values 必须在 annotation queries 运行前是完整 ALab object ids，同时保留 path/line target-id filtering 和合法 creator experiment filtering。
- 收紧 untyped `audit list --object-id`，现在只接受完整 ALab ids 或稳定 audit literals `backups`、`cache`、`skydiscover`，并通过 generated no-side-effect coverage 证明 malformed short ids 会在 audit queries 前失败。
- 将 `audit list --action` 收紧到文档定义的 generic audit action set，使 unsupported action filters 现在会在 audit queries 前以稳定 `CONFIG_INVALID` 失败，而不是返回空的 success result。
- 将 `audit list --object-type` 收紧到文档定义的 audit object-type set，使 unsupported object-type filters 现在会在 audit queries 前、也在 object-id filter interpretation 前以稳定 `CONFIG_INVALID` 失败。
- 将 `runs list --commit` 收紧为必须使用 hexadecimal commit SHA prefix，并按 prefix 匹配 stored full commit ids；`HEAD` 这类 arbitrary moving refs 现在会在 run record scans 前以稳定 `CONFIG_INVALID` 失败，而不是返回空的 success result。
- 将 `runs list --runner-type` 收紧到 V1 runner config type set `local`、`docker`、`harbor`、`skydiscover_docker` 和 `skydiscover_python`，使 unsupported runner filters 现在会在 run record scans 前以稳定 `CONFIG_INVALID` 失败，而不是返回空的 success result。
- 将 `artifacts list --root` 收紧到 storage-defined artifact roots `workspace` 和 `run`，使 unsupported artifact root filters 现在会在 artifact queries 前以稳定 `CONFIG_INVALID` 失败，而不是返回空的 success result。
- 将 `artifacts list --content-hash` 收紧到 stored artifact content-hash shape `sha256:<64-hex>`，使 malformed hash filters 现在会在 artifact queries 前以稳定 `CONFIG_INVALID` 失败，而不是返回空的 success result。
- 将 `logs list --stream` 收紧到 storage-defined stream set `stdout`、`stderr`、`hidden_stdout` 和 `hidden_stderr`，使 unsupported log stream filters 现在会在 log queries 前以稳定 `CONFIG_INVALID` 失败，而不是返回空的 success result。
- 将 `exp token list|revoke|regenerate --mode` 收紧到 shared token-mode choice set `worktree|inspection`，使 malformed token-mode selectors 现在会在 token queries 或 regeneration writes 前，通过 generated typed-value no-side-effect contract 以稳定 `CONFIG_INVALID` 失败。
- 将 `exp create --visibility-scope` 收紧到 documented visibility scope set `none|same_project|explicit`，把它纳入 generated typed-value no-side-effect contract，并让 CLI specs 直接列出具体 mutable/visibility options，而不是依赖 prose。
- 将 experiment list/search/best `--status` 收紧到 shared experiment status set `open|closed|archived`，记录 accepted values，并让 malformed values 通过 generated typed-value no-side-effect contract 处理。
- 将 `key create --role` 收紧到 shared key-role choice set `admin`，记录 accepted value，并让 malformed roles 在 admin credential writes 前通过 generated typed-value no-side-effect contract 处理。
- 将 `catalog skydiscover add|update --commit` 收紧为在 catalog clone/fetch/update work 前校验文档要求的 full-SHA shape，并把 malformed selector 纳入 generated typed-value no-side-effect contract。
- 将 `exp create --from-commit` 和 `exp checkout --commit` 收紧为通过 shared commit-selector parser 拒绝 malformed non-SHA custom selectors，确保在 experiment inheritance lookup、checkout path registration、worktree creation 或 audit writes 前失败，并把两个 selector 纳入 generated typed-value no-side-effect contract。
- 将 generated typed-value contract 从 malformed types 扩展到 invalid numeric ranges，覆盖 retention、pagination 和 audit pagination values，包括负数 `--keep`/`--older-than`、越界 observe `--limit`、负数 observe `--offset`，以及 invalid audit `--limit`/`--offset`。
- 将 `backup prune --keep` parsing 前移到 backup file enumeration 之前，使 malformed 或 negative keep counts 在 backup glob/stat work、deletion decisions 或 audit writes 前失败。
- 将 generated source-limit typed-value contract 扩展到 negative `--max-files`、`--max-total-bytes` 和 `--max-file-bytes`，证明 `project init`、`source import` 和 inline `exp create` 会在 source staging 或 persistence work 前拒绝 invalid limits。
- 将 public inline source policy-ceiling validation 前移到 temporary source work creation 之前，使 no-key caller 将 limits 提高到 `[public_source_import]` 以上时，会在 source path reads、copies、Git clones、source rows、experiment rows 或 worktree creation 前失败。
- 将 artifact list `--size-min` 和 `--size-max` filters 收紧为 non-negative integer byte counts，同步文档边界，并纳入 generated typed-value no-side-effect contract，确保在 artifact queries 运行前失败。
- 将 `--config-version` observe filters 与 project config `--version <n>` selectors 收紧为正整数 retained config version numbers，并为 experiment/run observe filters 增加 generated no-side-effect typed-value coverage，为 project config reads 增加 selector lookup 前的 smoke coverage。
- 将 observe numeric range filters 收紧为有序区间，使 experiment/run lists 中倒置的 `--reward-min`/`--reward-max` 组合，以及 artifact lists 中倒置的 `--size-min`/`--size-max` 组合，在 query execution 前以 `CONFIG_INVALID` 失败，而不是静默返回空结果。
- 将 time range filters 收紧为有序区间，使 audit、experiment、run、artifact、log 与 annotation lists 中倒置的 matching `after`/`before` 组合在 query execution 前以 `CONFIG_INVALID` 失败，同时保留既有 RFC 3339 offset 和 malformed timestamp 检查。
- 收紧 export output path validation，使 `project config export`、`artifacts export` 和 `logs export` 即使提供 `--overwrite` 也会以稳定 `OUTPUT_EXISTS` 拒绝 directory targets，而不是落入 filesystem write errors。
- 收紧 `exp create` default worktree path validation，使已经存在的 default path（包括空目录）会在 source import、worktree creation、token writes、path registration 或 experiment rows 前，以稳定 `OUTPUT_EXISTS` 和 `--path` next action 失败；显式 custom `--path` 仍接受空目录。
- 收紧 `--value-file`、`--summary-file`、`--feedback-file` 和 `--body-file` 的 text input file handling，使 missing、directory、unreadable 或 non-UTF-8 targets 会以稳定 `CONFIG_INVALID` 失败，而不是落入 internal file errors；失败发生在 secret writes、submission rows、annotation rows、runner execution 或 lifecycle audit rows 之前。
- 收紧 local runner sanitized environment setup，使 `env_mode = "sanitized"` 会在 process start 前创建 operation temporary `home/` directory，同时保留 inherited `ALAB_*` credential stripping 和 injected internal `ALAB_*` operation variables。
- 收紧 local runner 与 artifact-capture path containment，使 `runner.working_directory` 和 resolved artifact paths 使用 normalized path ancestry 而不是 string-prefix matching，避免带有 sibling prefix 的路径被误判为位于 workspace 或 artifact root 内。
- 收紧 file reward parsing，使 `reward.path` 只接受 `workspace:` 和 `run:` roots，拒绝从所选 root normalized 或 symlink escape 的路径，执行 artifact per-file read limit，按 top-level `primary_metric` 解析 JSON reward objects，并拒绝 non-finite numeric values。
- 收紧 project config schema path validation，使 `runner.working_directory`、`runner.dockerfile`、`runner.context`、`runner.program_path`、file `reward.path` 和 artifact globs 在 config persistence 或 runner execution 前拒绝 absolute paths、unsupported artifact/reward roots 和 lexical `..` escapes；source-dependent path existence 仍延迟到 saved run/validation failures 记录。
- 收紧 project config schema limit validation，使 artifact capture 和 log byte limits 在 reward parsing、artifact capture 或 log storage 观察到 ambiguous limits 前拒绝 zero、negative 和 boolean values。
- 收紧 stdout-regex reward schema validation，使 invalid regular expressions 以及既没有 named `reward` group、也没有 capture group 的 patterns 会在 runner execution 前失败；runtime parsing 现在也遵循文档约定的优先 `reward` group、否则回退 first capture 的顺序。
- 收紧 project config numeric schema validation，使 runner timeout 拒绝 booleans 和 strings 而不是 coercion，Docker CPU limits 必须是 positive finite numbers，Docker memory limits 必须是 positive integers，public source-import policy limits 必须是 non-negative integers。
- 收紧 runner command schema validation，使显式提供的 `runner.command` list 必须至少包含一个 non-empty argv entry，显式提供的 `runner.shell` 必须包含 non-whitespace text，失败发生在 runner execution 前。
- 增加 runner shell contract coverage，覆盖 V1 runner boundary：local shell mode 有 direct `/bin/sh` execution test 并验证 ALab env injection；Docker shell mode 现在有 fake-Docker argument-shape coverage，证明 ALab 会在 image 后追加 `/bin/sh -c <shell>`；Harbor/SkyDiscover adapter runner configs 会在执行前拒绝 user shell commands。
- 增加 runner environment isolation contract coverage，覆盖 V1 runner boundary：local `env_mode = "full"` 现在证明 host `ALAB_*` credentials 会被剥离，同时 non-ALab host env 会按文档继承并产生 warning；Docker runner fake-CLI coverage 证明 container env 不继承 host env，且 internal ALab operation variables 会覆盖冲突的 `[env]` values。
- 增加 runner input/context isolation coverage：local runner 现在有 direct closed-stdin contract test；CLI smoke test 证明 experiment runs 会从 clean temporary runner workspace 执行，即使 experiment worktree 中存在 `.alab/context.json` 和 `.alab/token`，runner workspace 也看不到这些文件。
- 实现文档要求的 local runner process-group timeout behavior：local runners 现在会在 separate session 中启动；timeout handling 会先向 process group 发送 `SIGTERM`，短暂等待后必要时发送 `SIGKILL`；regression coverage 证明 timed-out runner 启动的 child process 不会在 timeout 后继续存活并写文件。
- 将 `stdout_regex` reward parsing 对齐到文档定义的 observable stdout contract：regex rewards 现在从 redacted stdout 中解析，并受 `logs.stdout_limit_bytes` 截断限制，因此被 secret redaction 隐藏或位于 stored stdout limit 之后的 reward 不能从 otherwise invisible bytes 中解析出来。
- 将 artifact capture 对齐 documented glob semantics：directory matches 现在会递归展开为 file artifact records；来自多个 globs 的 matches 会按 resolved path 去重，并在 capture 与 limit accounting 前按 normalized relative path 排序；symlink escapes 会记录为 `skipped` artifact rows，而不是静默丢弃。
- 将 artifact capture error visibility 对齐 V1 warning contract：capture `error` artifact rows 现在会向 saved run/validation records、run/show output、project config baseline output 和 project validation output 添加稳定 `ARTIFACT_CAPTURE_ERROR` warning，且不改变 execution status。
- 增加 V1 exact-artifact-bytes contract 的 default-suite warning coverage：配置 active `secret_env` values 与 artifact globs 时，现在证明 project init、manual validation、config baseline validation、run 和 observe-run output 会 render `ARTIFACT_BYTES_NOT_REDACTED`，validation/run `record_json` 会持久化该 warning，同时 stdout previews 保持 redacted，artifact export 返回 exact bytes。
- 收紧 `secret_env` config validation，使 raw values 必须是 valid single-line secret strings，retain markers 会拒绝 unknown keys 和 malformed fingerprints，从 user config files 拒绝 stored `{secret_value_id, fingerprint}` markers，并且 config-import dry run 现在会在不写入 rows 的情况下检查 retain-marker fingerprint mismatch。
- 收紧 project policy schema validation，使 public booleans 拒绝 string coercion，mutable include/exclude patterns 拒绝 empty 或 multiline entries，explicit visibility lists 要求 complete experiment ids，且 non-explicit visibility scopes 不能保留 ignored experiment ids。
- 收紧 global config validation，使手工编辑的 `config.toml` 会拒绝 boolean `schema_version`、unknown top-level keys、unknown `[output]`、`[storage]` 或 `[locks]` fields，以及 non-table section values，而不是静默忽略或落入 internal attribute errors。
- 收紧 stored experiment policy JSON validation，使 mutable policy arrays 拒绝 empty include sets 和 empty/multiline patterns，visibility schema versions 拒绝 booleans，explicit visibility 要求 complete experiment ids，且 non-explicit scopes 不能保留 ignored id arrays。
- 收紧 shared stored JSON contract validation，使 boolean `schema_version` 不再能作为 integer `1` 通过，并为 runtime capability details、catalog metadata 和 cache metadata 增加 typed validators，覆盖 safe-summary、string-array、object 与 non-empty inputs-hash checks。
- 收紧 annotation target JSON 与 CLI path-target validation：repo paths 必须是 normalized forward-slash relative paths，不能包含 absolute、Windows-absolute、empty、`.`、`..`、backslash、NUL 或 newline components；line ranges 现在拒绝 boolean start/end values，并要求 positive inclusive ranges；object target ids 必须是匹配 target type 的 complete ids；experiment object targets 必须匹配 `exp_id`；path/line target ids 必须匹配 `exp_id:commit:repo_path`。
- 按 V1 experiment-binding contract 收紧 annotation authoring：没有 resolved experiment id 的 validation-owned artifact targets 现在会在写入 annotation rows 或 revisions 前以稳定 `CONFIG_INVALID` 失败；annotation add/edit 继续拒绝包含 active `secret_env` values 的 body；private annotation visibility/editability 不再为 experiment tokens 扩大 target visibility。Collaboration smoke coverage 现在验证：当 current project visibility 不再暴露 peer target 时，指向该 peer experiment 的 private annotation 会变为不可见且不可编辑，并且不会写入新 revision。
- 收紧 annotation storage DDL：annotations 现在 enforce documented target/status/creator enums、positive current revisions，以及 path/line targets 的 non-null resolved commits；annotation revisions enforce positive revision numbers 和 root/admin/token creators。
- 收紧 artifact 和 log storage DDL：artifact rows enforce documented roots、statuses、owner exclusivity、capture/error payload shape、archive timestamp state 和 non-negative sizes；log rows enforce documented streams、hidden/visible consistency、owner exclusivity、archive timestamp state、boolean flags 和 stored byte bounds。
- 收紧 run 和 validation storage DDL：active records 不能保留 archived timestamps，non-running execution records 必须携带 `ended_at`，同时保留 runner-start errors、interrupted records 和 skipped validations 中 `exit_code` 与 `reward_value` 可为 null 的 documented behavior。
- 收紧 project/source/experiment storage DDL：project archive status 必须保留 valid pre-archive state；inherited config versions 必须指向 inherited validation，non-inherited versions 不能保留该引用；sources 必须保存 canonical `alab/source/<source_id>` ref；experiments 现在 enforce documented archive pre-state、closed timestamp visibility 和 all-or-none final-run removal metadata。
- 收紧 foundation storage DDL：credentials enforce root/admin/token row shape；path registry rows enforce context ownership 与 active/removed timestamp state；catalogs enforce V1 `skydiscover` key/type/status values；cache entries enforce V1 kind/status values 和 non-negative sizes。
- 收紧 audit/secret/submission/tag storage DDL：audit reasons enforce 文档定义的 65536-byte text limit；secret values 拒绝 non-text、NUL-containing 和 too-short values，并要求 HMAC-style fingerprints；submission message/summary/feedback fields enforce 文档定义的 byte limits；experiment tags enforce normalized lowercase ASCII slug shape 和 size。
- 收紧 catalog/cache storage DDL 与 specs：active/removed rows 必须让 `removed_at` 与 lifecycle state 一致；Docker image cache rows 必须存 `docker_tag` 而不是 `path`；SkyDiscover Python environment 与 trash cache rows 必须存 `path` 而不是 `docker_tag`。
- 实现文档要求的 experiment run/submit operation lock：现在通过 `locks` table 串行化同一 experiment 的 run/submit；未过期的同 experiment run/submit lock 会快速以 `EXPERIMENT_BUSY` 失败；过期 lock 会在 acquire 时被替换；长时间 runner execution 不包在 SQLite write transaction 中；成功或失败都会释放 lock。
- 对齐 run lifecycle ordering 与 V1 contract：dirty-scope checks 之后现在会在 ALab auto-commit 前分配并写入 `running` run row；auto-commit 使用该 run id 写 trailers；full-diff scope failures 会把该 row 更新为 `error`；runner/log/artifact capture 现在在 SQLite write transaction 外执行，最后再用一个短事务持久化结果。
- 收紧 ALab auto-commit identity：run-created commits 现在会从 experiment bound `[git]` config 显式设置 Git author 与 committer，即使外层 process environment 中存在冲突的 `GIT_AUTHOR_*` 或 `GIT_COMMITTER_*` variables。
- 收紧 staged-trash 与 Git-ref transaction failure handling：filesystem 或 ref staging 之后发生 non-ALab audit/DB failure 时，现在会恢复 staged trash paths 与已删除的 source/experiment refs，再以稳定 `STORAGE_ERROR` 和文档要求的 repair next action 返回，而不是泄露 raw internal failures；worktree、source、experiment、inspection checkout、project whole-tree、validation cascade、artifact、log 与 run cascade remove 新增 regression coverage，证明 DB/token/path rows、Git refs、lifecycle metadata 与 filesystem contents 都保持完整。
- 收紧 project-context repair authentication：ambient `ALAB_KEY` 现在可以满足 project marker repair 的 documented root/admin path；experiment 和 inspection repair 仍会忽略 ambient admin/root key，并要求严格的 self-token branch 或 pinned-commit checks。
- 收紧 public project capability fallback：invalid project status 在 ambient credentials 和 explicit non-admin keys 下都会保持缩减的 public-invalid field set；public `exp create` 在 policy 允许时会把有效但不匹配 target project 的 explicit credential 当作 public caller，而 `project.allow_public_exp_create = false` 时仍会隐藏并 preflight-block。
- 增加 generated invalid explicit-credential runtime matrix，覆盖每个 registered command 的 `--key` 与 `--key-stdin`，证明 `AUTH_DENIED` 会发生在 handler option parsing、缺失 payload-file 读取、output-parent 创建、SQLite mutation、global config/context marker 变化或 filesystem/cache tree 变化之前。
- 增加 opt-in live SkyDiscover catalog hardening：通过 `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1` 运行的测试会 probe official remote，clone 并 pin `main`，证明 `catalog show` 不运行 Git 或访问网络，自动发现 live catalog 中真实的 Python/Docker evaluator ref，并通过 `project init skydiscover --source-empty --skip-baseline-test` 解析它，同时不向默认 suite 增加 network dependency。
- 扩展 opt-in networked SkyDiscover Python dependency hardening：通过 `ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1` 运行时，evaluator matrix 现在会用 `uv` 从 configured Python package index 安装 direct `six==1.16.0` dependency 和 transitive `python-dateutil==2.9.0.post0` dependency set，在 hidden evaluator environments 中 import，验证 reward/feedback capture，并证明 per-dependency environment cache hits，同时不改变既有 local-wheel real-environment path。
- 增加 opt-in native/binary SkyDiscover Python dependency hardening：通过 `ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1` 运行时，evaluator 会从 configured Python package index 安装 configurable native package，默认是 `orjson>=3.10,<4`，在 hidden evaluator environment 中 import，通过 binary serialization/deserialization 验证 metric capture，并证明第二次运行命中 environment cache。
- 增加 default-suite saved SkyDiscover Python dependency-failure 覆盖，使用 fake `uv`：baseline 期间 evaluator dependency installation 失败时会创建 invalid project、保存 validation `error` record 并输出 `BASELINE_VALIDATION_FAILED`；同样的失败发生在 `run` 期间时会保存 run `error` record 并输出 `RUNNER_ERROR`。两条路径都以 exit `1` 返回，把 setup output 存进 hidden logs，且不会暴露 internal/system error。
- 增加 default-suite saved run result-failure 覆盖，包含 local `RUNNER_FAILED`、`RUNNER_TIMEOUT` 与 `RUNNER_ERROR`：矩阵证明每种失败都会以 exit `1` 返回，先渲染正常 `run` object fields，再追加 `error code`、result-level `exit code`、`reason` 与 `next`；result failure 在 debug 模式下不输出 traceback；同时持久化匹配的 run status、exit、reward-parse 与 failure metadata，并保证 observe-run rendering 与已保存 row 对齐。
- 增加 default-suite saved validation result-failure 覆盖，包含 manual `project validate` 的 failed、timeout 与 runner-error records：矩阵证明每种 saved validation failure 都会以 exit `1` 返回，先渲染文档定义的 `validation` object fields，再追加 `BASELINE_VALIDATION_FAILED`、result-level `exit code`、status-derived `reason` 与 `next`；debug 模式下不输出 traceback；同时持久化匹配的 validation status、exit、reward-parse 与 failure metadata，并保留之前的 active valid project version 与 validation id。
- 增加 default-suite submit result-failure 覆盖，包含 final-run `RUNNER_FAILED`、`RUNNER_TIMEOUT`、`RUNNER_ERROR` 以及缺少 reusable passed run：矩阵证明每个 rejected submission 都会以 exit `1` 返回，先渲染文档定义的 `submission` fields，再追加 diagnostics；experiment 保持 open 且没有 final run/commit、不写 submission row；发生 rerun 时会保存失败 run record；debug 模式下不输出 traceback。
- 增加 default-suite baseline result-failure 覆盖，包含 `project init`、`project config set` 与 `project config import` 中 failed、timeout 和 runner-error validation records：矩阵证明每个命令都会以 exit `1` 返回，先渲染各自文档定义的 primary object fields，再追加 `BASELINE_VALIDATION_FAILED` diagnostics；debug 模式下不输出 traceback；同时持久化匹配的 validation/config/project state，并在 config mutation 失败时保留之前的 active valid project version。
- 修复 `project env set|unset` 与 `project secret set|unset` baseline result-failure rendering，使它们保留 shared config mutation flow 追加的 `BASELINE_VALIDATION_FAILED` fields，而不是丢弃这些字段；同时增加 default-suite 矩阵覆盖四个 mutation surface 的 failed、timeout 与 runner-error records，并包含 raw-secret non-rendering 检查。

仍未完成：

- 这些 contracts 证明 registry、alias、primary object-type metadata、selected global-auth/global-config/project/project-lifecycle/config/source/source-lifecycle/catalog/credential/experiment-token/env/secret/experiment/experiment-observe/experiment-lifecycle/experiment-remove/experiment-worktree/inspection-checkout/run/submit/artifact/log/annotation/audit/secret-gc/validation/validation-lifecycle/lock-clear/maintenance-prune/context diagnostics/status success-field ordering，包括 raw credential one-time rendering rules、raw token write/non-rendering rules、token file private-permission writes、token Git-exclude refresh、token permission warning output、global `config validate` object schemas、observe experiment search/best、observe run/artifact/log archive/unarchive、artifact/log export、run/artifact/log remove dry-run/actual schemas、`RUNNER_FAILED`、`RUNNER_TIMEOUT` 与 `RUNNER_ERROR` 的 saved run result-failure output、failed、timeout 与 runner-error records 的 saved manual validation result-failure output、failed/timeout/error final reruns 与 missing reusable passed runs 的 submit result-failure output、`project init`/`project config set`/`project config import` 中 failed、timeout 和 runner-error records 的 baseline result-failure output、带 raw-secret non-rendering 的 `project env` 与 `project secret` mutation baseline result-failure output，以及 read/export 和 lifecycle top-level observe alias behavior；docs-derived stable error-code catalog、numeric exit-code table、exit mapping、warning-code catalog 与 representative object-specific not-found selectors；representative write targets 的稳定 `HOME_EXISTS`/`OUTPUT_EXISTS` error blocks；reusable persisted-JSON 与 context-marker contract validation、project config、credential/audit/source-origin/experiment metadata and policy/submission refs/execution record/annotation target and visibility/runtime capability/catalog metadata enforcement 以及 cache metadata writer alignment；default fake-Docker Harbor shared/separate verifier runner coverage、hidden-log redaction 与 Dockerfile cache metadata；representative selectors 的完整 ALab object id enforcement；representative filter families 的 RFC 3339 time-filter parsing；internal failures 与 ordinary command errors 的 debug traceback gating；context-sensitive status object rendering；capability-surface；ambient-key display isolation；explicit-root/admin display behavior，包括 project-context repair 可通过 ambient `ALAB_KEY` 认证且不会扩大 experiment/inspection self-repair；generated global-option pre-scan error rejection before home creation、generated explicit invalid-credential rejection before handler payloads、generated standalone-separator global pre-scan stop behavior 且无 stdin/home/state side effects，以及 global 和 command-local value-option missing-value rejection、shared typed value-parser malformed-value rejection，包括下一个 token 看起来像 `--...` option 的情况，以及 generated registered command-local absent-value no-side-effect coverage、project config/env/secret dry-run/skip-baseline conflict rejection before payload reads、documented non-remove conflict rejection 且无 DB/config/marker/token/tree 或 payload-file side effects，并包含 direct/helper-mediated literal value-option reads 与 registered handler positional validators 的 static registration coverage；`--key-stdin` input validation、display 与 read-command execution equivalence；admin project-scope preflight；explicit-key context-conflict precedence；project/experiment/inspection-context help behavior；help-schema；default/selected/top-level help availability；locked-preflight before handler argument effects；nested-help/preflight decision parity for handler payloads；generated explicit-credential、project-context、experiment-context 与 inspection-context unavailable-command preflight rejection 且无 handler parsing/file-read/output-write/DB/marker/token/filesystem side effects；global-public unsupported-option pre-side-effect behavior；all-registered-command unsupported-option runtime rejection 且无 DB/config/marker/token side effects；generated all-registered-command trailing-global placement before handler errors 且无 DB/config/marker/token side effects；generated zero-positional extra-argument runtime rejection 且无 DB/config/marker/token/source/cache/export/worktree side effects；generated single-selector extra-argument 和 missing-required-selector runtime rejection 且无 DB/config/marker/token/source/cache/export/worktree side effects；generated fixed-count positional extra-argument 和 missing-required-positional runtime rejection 且无 config/source/secret/tag/audit side effects；command-local singleton option duplicate guarding 与 explicit repeated-option classification；generated registered command-local singleton duplicate-option runtime rejection 且无 availability/selector/file-read/DB/config/marker/token side effects；generated registered-command success-field documentation coverage 及 English/Chinese synchronization，包括 alias handler inheritance；generated hard-remove force-confirm guard rejection 且无 DB/config/marker/token/path side effects；generated dry-run-capable hard-remove preservation 且无 DB/marker/token/path/trash side effects；generated actual hard-remove lifecycle-blocker rejection 且无 DB/marker/token/path/trash side effects；generated actual hard-remove dependency-blocker rejection 且无 DB/marker/token/path/project-tree/trash/source-ref side effects；generated mixed dry-run/force-confirm hard-remove rejection 且无 DB/marker/token/path/project-tree/trash side effects；future dry-run plus force-confirm handlers 的 static mixed-mode guard coverage；两份 CLI specs 的 docs-derived mixed-mode conflict declarations；English/Chinese conflict-option equivalence；per-handler known-option structure、literal option-read allowlist coverage、English/Chinese docs-derived documented-option acceptance、English/Chinese documented-option equivalence、English/Chinese command-surface coverage against the registry，以及 selected English/Chinese success-field equivalence。它们不能取代仍需补充的 broader generated golden matrix，用于完整 command-specific success/error rendering，以及 saved baseline/env-secret/run/validation/submit result-failure output、unsupported-option、positional extra-argument rejection、explicit invalid-credential rejection、force-confirm guard rejection、command-local duplicate-option rejection、value-option missing-value rejection、typed value-parser malformed-value rejection、config/env/secret dry-run/skip-baseline conflict rejection、documented non-remove conflict rejection、dry-run hard-remove preservation、actual hard-remove lifecycle blockers、dependency blockers 和 mixed remove-mode rejection 之外的 no-side-effect behavior。
- 更广泛的 package-index variability 仍属于 default suite 之外的 opt-in environment concern。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_local_runner_shell_mode_runs_through_sh tests/test_runner_local.py::test_project_config_schema_rejects_empty_runner_command_and_shell tests/test_runner_docker.py::test_docker_runner_shell_uses_container_sh -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_full_local_runner_strips_alab_credentials_and_internal_env_overrides tests/test_runner_docker.py::test_docker_runner_env_is_hostless_and_internal_env_overrides_config_env -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_local_runner_stdin_is_closed tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_local_runner_timeout_terminates_child_process_group -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_stdout_regex_reward_uses_redacted_and_truncated_stdout -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_local.py tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_local.py tests/test_runner_docker.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_skydiscover.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_skydiscover_python.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_skydiscover_python.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_env_secret_baseline_result_failures_follow_cli_spec tests/test_cli_contract.py::test_project_baseline_result_failures_follow_cli_spec tests/test_cli_contract.py::test_project_secret_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_env_success_fields_follow_cli_spec tests/test_smoke.py::test_project_secret_input_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_audit_secret_submission_and_tag_ddl_contract_checks_are_enforced tests/test_migrations.py::test_project_source_and_experiment_lifecycle_ddl_contract_checks_are_enforced -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_foundation_table_ddl_contract_checks_are_enforced tests/test_migrations.py::test_cache_entry_metadata_writers_use_safe_json_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_context_repair_accepts_ambient_admin_key tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_maintenance_prune_success_fields_follow_cli_spec tests/test_migrations.py::test_foundation_table_ddl_contract_checks_are_enforced -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts tests/test_cli_contract.py::test_maintenance_prune_success_fields_follow_cli_spec -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_run_enforces_experiment_mutable_scope -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_checkout_remove_reconciles_missing_path -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_source_remove_restores_deleted_ref_after_transaction_failure tests/test_smoke.py::test_experiment_remove_restores_branch_and_trash_after_transaction_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_source_remove_restores_deleted_ref_after_transaction_failure tests/test_smoke.py::test_experiment_remove_restores_branch_and_trash_after_transaction_failure tests/test_smoke.py::test_checkout_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_project_remove_restores_whole_tree_trash_after_transaction_failure tests/test_smoke.py::test_validation_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_observe_remove_restores_staged_trash_after_transaction_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_catalog.py -q`
- `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_catalog.py -q`（除非 `git` 和 live SkyDiscover remote 可用，否则 skip）
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py -q`
- `ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_python.py::test_networked_skydiscover_python_dependency_install -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_foundation_table_ddl_contract_checks_are_enforced tests/test_migrations.py::test_removed_path_registry_rows_do_not_block_path_reuse -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_project_source_and_experiment_lifecycle_ddl_contract_checks_are_enforced tests/test_migrations.py::test_required_storage_tables_and_columns_are_created -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced tests/test_migrations.py::test_run_records_allow_required_nullable_fields -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_secret_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_env_success_fields_follow_cli_spec tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_artifact_and_log_ddl_contract_checks_are_enforced tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced tests/test_migrations.py::test_required_storage_tables_and_columns_are_created -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_annotation_target_and_visibility_json_contracts tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_experiment_create_default_worktree_path_must_be_missing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_explicit_credentials_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_experiment_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_inspection_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_stop_global_prescan_at_standalone_separator_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_source_origin_metadata_contract_enforces_documented_shape tests/test_smoke.py::test_public_exp_create_inline_source_import -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_annotation_target_and_visibility_json_contracts tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_experiment_metadata_contract_enforces_documented_shape tests/test_cli_contract.py::test_experiment_create_source_ref_success_fields_follow_cli_spec tests/test_cli_contract.py::test_experiment_create_inline_source_variants_success_fields_follow_cli_spec tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_experiment_policy_json_contract_enforces_documented_shape tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_execution_record_json_contract_enforces_documented_shape tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_debug_does_not_trace_saved_result_failures -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_audit_json_contracts_enforce_documented_shape tests/test_cli_contract.py::test_audit_success_fields_follow_cli_spec tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_submission_refs_json_contract_enforces_documented_shape tests/test_cli_contract.py::test_submit_success_fields_follow_cli_spec tests/test_smoke.py::test_local_project_run_submit_workflow -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_project_config_json_contract_enforces_documented_shape tests/test_smoke.py::test_project_secret_input_contract tests/test_cli_contract.py::test_project_config_show_export_never_render_raw_secret_values -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_english_and_chinese_conflict_option_contracts_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_dry_run_force_confirm_remove_docs_declare_mixed_mode_conflict -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_context_token_file_permission_warning_renders_after_primary_result tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_cli_token_writes_use_private_permissions_and_git_exclude -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_known_options_are_duplicate_guarded_or_explicitly_repeatable tests/test_cli_contract.py::test_logs_show_rejects_duplicate_include_hidden_before_lookup -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_representative_singleton_duplicate_options_fail_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_singleton_options_reject_duplicates_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_value_options_reject_option_tokens_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_non_remove_documented_conflicts_fail_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_harbor_runner_separate_verifier_image tests/test_real_docker.py::test_real_harbor_runner_separate_verifier_tests_dockerfile -q`（除非设置 `ALAB_RUN_REAL_DOCKER=1` 且 Docker/images 可用，否则 skip）
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_handlers_validate_positional_arguments -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_zero_positional_commands_reject_extra_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_single_selector_commands_reject_extra_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_required_single_selector_commands_reject_missing_selector_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_fixed_positional_commands_reject_extra_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_fixed_positional_commands_reject_missing_required_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_known_options_are_duplicate_guarded_or_explicitly_repeatable tests/test_cli_contract.py::test_known_option_allowlists_cover_literal_option_reads tests/test_cli_contract.py::test_literal_value_option_reads_are_registered_for_positional_parsing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_known_option_allowlists_cover_literal_option_reads tests/test_cli_contract.py::test_literal_value_option_reads_are_registered_for_positional_parsing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_have_success_field_contracts_in_cli_specs tests/test_cli_contract.py::test_registered_command_success_field_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_context_marker_json_contract_enforces_documented_shape tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_cli_contract.py::test_project_read_command_success_fields_follow_cli_spec -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_reject_unsupported_options_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_accept_trailing_globals_before_handler_errors_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_force_confirm_commands_reject_incomplete_confirmation_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_dry_runs_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_dry_run_force_confirm_remove_handlers_use_mixed_mode_guard -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_dry_run_force_confirm_remove_docs_declare_mixed_mode_conflict -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_registered_commands_reject_unsupported_options_without_side_effects tests/test_cli_contract.py::test_known_option_allowlists_cover_literal_option_reads tests/test_cli_contract.py::test_registered_command_handlers_gate_unknown_options -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_observe_lifecycle_aliases_render_canonical_shapes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_rfc3339_time_filters_require_explicit_offsets tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_smoke.py::test_project_secret_input_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_smoke.py::test_capability_help_and_preflight_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_documented_command_options_are_accepted_by_registered_handlers tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Global Config Failure Gate Hardening

已实现：

- 增加 CLI entrypoint global-config gate，使 invalid persisted `config.toml` 现在会以 `CONFIG_INVALID` 阻断 normal command 和 help execution，同时 `auth init` 与 `config show|set|reset|validate` 仍可用于 diagnosis 或 repair。
- 为无法 parse 的 global config TOML 增加明确 next action，提示使用 `alab config reset --all`。
- 扩展 smoke coverage，证明无法 parse 的 global config 会阻止 `config set`、field-level `config reset`、普通 authenticated command execution 以及无 command/`help`/`--help` rendering 重写或绕过损坏文件，同时 `config reset --all` 可恢复 defaults。
- 同步英文和中文 CLI/test specs，记录 invalid-global-config gate 与 unparseable-TOML repair contract。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_global_repair_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_output_rich_is_single_command_and_non_persistent tests/test_cli_contract.py::test_default_help_runtime_hides_locked_commands_without_creating_home tests/test_cli_contract.py::test_global_public_commands_reject_unsupported_options_before_home_creation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Migration Lock Timeout Hardening

已实现：

- 将 home-level migration lock 从 indefinite blocking 改为 nonblocking polling，并遵守 global config 中的 `locks.acquire_timeout_ms`；当 config missing 或 unreadable 时回退到 V1 default。
- 当另一个进程持有 `.migration.lock` 超过 configured timeout 时，新增 `RESOURCE_BUSY` failure path，并渲染安全的 retry next action。
- 增加 migration coverage，证明短 configured timeout 会在打开或创建 `alab.db` 前失败，同时既有 default-timeout serialization behavior 仍会等待 lock release 后完成 migration。
- 同步英文和中文 test specs，要求覆盖 configured migration-lock timeout。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_migration_lock_serializes_migrate_processes tests/test_migrations.py::test_migration_lock_timeout_uses_global_config -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/db.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 SQLite Busy Timeout Config Wiring

已实现：

- 将 global config 中的 `storage.busy_timeout_ms` 接入 `Database.connect()`，使 ALab SQLite connections 使用配置的 `PRAGMA busy_timeout`，不再使用硬编码值。
- 合并 early storage setup 所需的 raw positive-integer global-config 读取逻辑，与 migration lock timeout configuration 共享 fallback-safe path。
- 增加 storage tests，证明 default busy timeout 仍为 `5000`，并且 configured value 会应用到新的 SQLite connections。
- 同步英文和中文 CLI/storage/test specs，记录 `storage.busy_timeout_ms` 是 SQLite busy-timeout control。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py::test_database_connections_use_wal_mode tests/test_migrations.py::test_database_connections_use_configured_busy_timeout tests/test_migrations.py::test_migration_lock_timeout_uses_global_config -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/db.py tests/test_migrations.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_migrations.py tests/test_cli_contract.py::test_error_exit_code_mapping_follows_cli_contract_tables tests/test_cli_contract.py::test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Global Config Gate Ordering Hardening

已实现：

- 将 CLI request construction 拆成用于 home/global-config gating 的 base request，以及用于 context detection 和 explicit credential lookup 的 hydrated request。
- 确保 non-repair commands 会在 context 或 explicit credential lookup 前加载并拒绝 invalid global config，因此 malformed `config.toml` 不会被坏的 `--key` 掩盖。
- 保留既有 help credential contract：gate 前只做 lightweight help-request detection；当 config valid 时，完整 help option parsing 仍在 explicit credential validation 后运行。
- 扩展 smoke coverage，证明 global config TOML 损坏时，即使 explicit key 是坏的也仍返回 `CONFIG_INVALID`，并同步英文和中文 test specs。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_debug_stack_trace_only_for_internal_errors tests/test_cli_contract.py::test_debug_mode_traces_only_internal_system_failures -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation tests/test_cli_contract.py::test_key_stdin_input_validation_is_strict_global_contract tests/test_cli_contract.py::test_default_help_runtime_hides_locked_commands_without_creating_home tests/test_cli_contract.py::test_ambient_key_does_not_broaden_help_capability_display tests/test_cli_contract.py::test_explicit_root_key_help_capability_display_follows_registry_credentials tests/test_cli_contract.py::test_explicit_admin_key_help_capability_display_is_project_scoped -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py tests/test_smoke.py tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check .`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Real Docker Adapter Cache-Hit Hardening

已实现：

- 扩展 opt-in real Docker Harbor `tests/Dockerfile` verifier test，使同一个 Dockerfile-backed verifier 连续运行两次，并要求第二次 real container execution 复用 ALab Docker image cache，`status = hit`。
- 扩展 opt-in real Docker SkyDiscover Docker evaluator test，使其记录 real Docker image-cache metadata，并要求第二次 evaluator execution 命中 cache。
- 同步英文和中文 test specs，在 full V1 opt-in Docker gate 中纳入 Dockerfile-backed adapter images 的 real Docker image-cache reuse。

验证：

- `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_harbor_runner_separate_verifier_tests_dockerfile tests/test_real_docker.py::test_real_skydiscover_docker_runner_evaluator -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Runner Status Text And Opt-In Test Docs Cleanup

已实现：

- 移除 `project init` 中过期的 adapter execution wording；Harbor 和 SkyDiscover project initialization 现在已经会解析 adapter-derived sources，并参与 baseline validation。
- 将过时的 runner fallback messages 从“该 milestone 未实现 non-local runners”改为精确的 unsupported-dispatch messages。
- 更新英文和中文 README 的 opt-in Docker test 说明，纳入 Dockerfile-backed adapter images 的 real Docker image-cache reuse。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py src/alab/services.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py src/alab/services.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Python Opt-In Environment Revalidation

已验证：

- 在当前环境中重新运行 full opt-in real SkyDiscover Python dependency suite，并启用 local-wheel、networked pure-Python、transitive dependency 和 native/binary dependency paths。
- 确认四个 real-environment cases 都能通过 configured package index 与 `uv` environment cache，包括 tests 内部的 cache-hit checks。

验证：

- `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest tests/test_real_skydiscover_python.py -q`

## 2026-05-21 README Opt-In Marker Contract

已实现：

- 新增 default-suite static contract：从 `pyproject.toml` 读取 pytest markers，从 `README.md` 和 `README_cn.md` 提取 `uv run pytest -m ...` opt-in commands，并扫描 `tests/` 中实际使用的 declared markers。
- 该 contract 现在要求英文 README commands、中文 README commands、declared pytest markers 和实际 opt-in test markers 保持同步。
- 同步英文和中文 test specs，记录这个 README/marker contract。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Host Support Policy Proof

已实现：

- 新增 `tests/test_cli_contract.py::test_host_support_policy_and_opt_in_runner_gates_are_documented`。
- 通过断言当前 host 为 macOS/Linux、blueprint 和中文 blueprint 将 Windows 排除在 V1 acceptance 之外、README/README_cn 记录 opt-in real runner commands，并且 `pyproject.toml` 保留 opt-in real runner markers，证明 current default/local scope 的 host policy row。
- Real Docker/Harbor/SkyDiscover validation 继续保持为 `ENV-GATED`。

验证：

- Focused host-policy checks 已纳入 batch 后的 docs/static validation run。

## 2026-05-21 Live SkyDiscover Catalog Revalidation

已验证：

- 在当前环境中对 official remote 重新运行 opt-in live SkyDiscover catalog test。
- 确认 live path 实际通过且没有 skip：catalog add/update 会 clone 并 pin exact commit，`catalog show` 保持 no-network，测试会发现 live catalog 中真实 evaluator ref，并通过 `project init skydiscover --source-empty --skip-baseline-test` 解析它。

验证：

- `ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_skydiscover_catalog.py -q`

## 2026-05-21 Markdown Chinese Pair Contract

已实现：

- 新增 default-suite static contract，扫描 repository-root 和 `docs/` Markdown files，并要求每个英文 Markdown source 都有同步的 `*_cn.md` pair。
- 同一 contract 会拒绝没有英文 source 的 orphan `*_cn.md` files，覆盖 `README`、`AGENTS`、`CORE`、blueprint、subsystem specs 和 progress documentation。
- 同步英文和中文 test specs，记录这个 documentation pairing requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 README Repository Structure Contract

已实现：

- 新增 default-suite static contract，解析 `README.md` 和 `README_cn.md` 中的 `Repository Structure` tree。
- 该 contract 要求英文和中文 README structure trees 在 path level 保持逐项同步，并验证每个列出的 repository path 都存在。
- 同步英文和中文 test specs，记录这个 README structure-tree requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `git diff --check`

## 2026-05-21 Local-Only Gitignore Contract

已实现：

- 新增 default-suite static contract，要求 `.gitignore` 持续忽略 local agent notes（`AGENTS.md`、`AGENTS_cn.md`、`CORE.md`、`CORE_cn.md`）。
- 同一 contract 要求真实 environment files（`.env`、`.env.*`）保持 ignored，同时保留 `!.env.example`，使 documented example configuration 可以被跟踪。
- 同步英文和中文 test specs，记录这个 local-only/sensitive-file ignore requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_local_agent_notes_and_env_files_are_gitignored tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Empty Ambient Key Handling

已实现：

- 调整 root/admin actor lookup，使空的 ambient `ALAB_KEY` 被视为未设置，而不是传给 credential verification。
- 这样用户加载未填 key 的 `.env.example` 后，需要 credential 的命令仍保持 documented `AUTH_REQUIRED` path。
- 增加 auth-level coverage，覆盖 missing 与 empty ambient `ALAB_KEY`，并同步英文和中文 CLI/test specs。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py::test_empty_ambient_alab_key_is_treated_as_absent tests/test_auth.py::test_credential_verification_requires_scope_project_status_mode_and_path tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_auth.py tests/test_smoke.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/services.py tests/test_auth.py tests/test_smoke.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Environment Example Contract

已实现：

- 新增 `.env.example`，作为 local ALab、uv、debug 和 opt-in validation environment variables 的集中 tracked example，同时继续 ignore 真实 `.env` files。
- 更新英文和中文 README setup sections 与 repository structure trees，引导 contributors 使用 `.env.example`。
- 新增 default-suite static contract，要求 `.env.example` 存在、拒绝重复 entries、检查 required local/opt-in environment keys，并验证 README 中所有 environment assignments 都已记录在 example file 中。
- 同步英文和中文 test specs 以及 local agent notes，记录新的 environment-example contract。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables tests/test_cli_contract.py::test_local_agent_notes_and_env_files_are_gitignored tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Empty Global Option Value Hardening

已实现：

- 收紧 CLI global pre-scan，使 `--home ""`、`--output ""` 和 `--key ""` 以 `CONFIG_INVALID` 失败，而不是继续进入 default home resolution、generic output validation 或 no-explicit-key capability behavior。
- 扩展 representative value-option test 以及 generated registered-command global-option matrix，覆盖 empty string values，同时保留原有 missing-value 和 option-looking-token failures。
- 同步英文和中文 CLI/test specs，记录 empty global option value rule。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_value_options_reject_option_tokens_without_side_effects tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation tests/test_cli_contract.py::test_key_stdin_input_validation_is_strict_global_contract -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/cli.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Command-Local Structural Empty Value Hardening

已实现：

- 增加 shared command-local value validation，使 selectors、paths、file paths、choices 和 numeric inputs 等 structural values 对 empty strings 输出稳定 `CONFIG_INVALID`。
- 保留 body、summary、feedback、message、reason、author labels、goal text 和 query filters 等 direct user-text 在 field-specific validators 允许 empty text 时的 empty-string 语义。
- 收紧 capability project-id probing，使 `--project ""` 在 availability checks 中不能静默 fallback 到当前 context。
- 更新 project init metadata overrides，使 `--goal ""` 被视为显式 empty goal override；project name 和 task fields 仍保持 non-empty enforcement。
- 扩展 representative value-option no-side-effect matrix，覆盖 exports、source import、experiment path/tag、token mode、annotation target、submit file input 和 SkyDiscover catalog origin URL 的 empty structural command-local values。
- 同步英文和中文 CLI/test specs，记录 structural values 与 user-text empty value 的区别。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_value_options_reject_option_tokens_without_side_effects tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py src/alab/services.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/cli.py src/alab/services.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Generated Structural Empty Value Matrix

已实现：

- 将 command-local structural empty-value contract 从 representative cases 升级为 generated registered-command matrix。
- 该 matrix 现在会对每个 registered command-local value option 验证 absent value，并对每个 structural command-local value option 验证 empty string value；已记录的 direct user-text fields 会被跳过，以保留其 intentional empty-string semantics。
- 复用既有 no-side-effect snapshot harness，使 generated empty-value checks 证明 rejection 前不会发生 DB/config/marker/token/tree/export/worktree mutations。
- 增加 static guard，确保 direct-user-text empty-value allowlist 始终位于 central value-option table 内。
- 同步英文和中文 test specs，记录 generated structural empty-value requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Unsupported Option Side-Effect Matrix Hardening

已实现：

- 收紧 generated unsupported command-local option matrix，使每个 registered non-help command 在执行 unsupported-option invocation 前都创建新的 SQLite snapshot、config/marker/token file snapshot，以及 project/source/tmp/worktree tree snapshot。
- 该 matrix 现在会逐命令证明 unsupported options 保持这些 snapshots 不变，而不是只在循环结束后检查 aggregate state。
- 同步英文和中文 test specs，记录 generated unsupported-option no-side-effect requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_reject_unsupported_options_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Global Pre-Scan Matrix Side-Effect Hardening

已实现：

- 收紧 generated trailing-global placement matrix，使每个 registered non-help command 在证明 trailing `--home`、`--key` 和 `--output text` 会先由 global pre-scan 消费之前，都建立新的 SQLite snapshot、config/marker/token file snapshot，以及 project/source/tmp/worktree tree snapshot。
- 用同样的逐命令 snapshots 收紧 generated standalone-`--` matrix，证明 `--` 后看起来像 global options 的 tokens 不会读取 `--key-stdin`、不会切换 homes，并且保持 DB/config/marker/token/tree/worktree state 不变。
- 同步英文和中文 test specs，记录更强的 global pre-scan no-side-effect requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_commands_accept_trailing_globals_before_handler_errors_without_side_effects tests/test_cli_contract.py::test_registered_commands_stop_global_prescan_at_standalone_separator_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Capability Preflight Matrix Side-Effect Hardening

已实现：

- 收紧 invalid explicit credential matrix，使每个 registered command 在 `--key` 和 `--key-stdin` invalid credentials 下，都会在证明 `AUTH_DENIED` 先于 handler payload parsing 短路前建立新的 SQLite snapshot、config/context file snapshot 和 project/source/tmp tree snapshot。
- 收紧 project、experiment 和 inspection unavailable-command preflight matrices，使每个 command/payload pair 都会在调用 command 前记录新的 DB/file/tree snapshots。
- 将 experiment 和 inspection token-context tree snapshots 扩展到包含 `sources`，以及 active worktree 或 inspection checkout，从而证明 command-unavailable preflight 不会在 immediate output path 之外发生 hidden staging。
- 为这些 matrices 增加明确的 DB、watched-file 和 watched-tree preservation failure diagnostics。
- 同步英文和中文 test specs，记录 fresh per-command/per-payload preflight snapshot requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_project_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_experiment_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_inspection_context_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Positional Matrix Side-Effect Hardening

已实现：

- 收紧 generated zero-positional、single-selector、required-selector、fixed-count extra 和 fixed-count missing positional matrices，使每个 registered-command case 都会在 invocation 前建立新的 SQLite snapshot、watched config/context/token file snapshot，以及 project/source/tmp/worktree tree snapshot。
- 为 positional validation 在 handler side effects 前失败时的 DB、watched-file、watched-tree、export、checkout 和 worktree preservation 增加 per-command diagnostics。
- 在更大范围的 positional edit 暴露旧 aggregate-snapshot assumption 后，将 annotation target-id preflight matrix 也升级为同样的 fresh per-case snapshot pattern。
- 同步英文和中文 test specs，记录 fresh per-command positional snapshot requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_zero_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_single_selector_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_required_single_selector_commands_reject_missing_selector_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_missing_required_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads tests/test_cli_contract.py::test_zero_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_single_selector_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_required_single_selector_commands_reject_missing_selector_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_extra_positional_without_side_effects tests/test_cli_contract.py::test_fixed_positional_commands_reject_missing_required_positional_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Hard Remove Matrix Side-Effect Hardening

已实现：

- 收紧 hard-remove confirmation matrix，使每个 command 以及 missing-force、missing-confirm、wrong-confirm variant 都会在 invocation 前建立新的 SQLite、watched-file、tree 和 trash snapshots。
- 收紧 hard-remove dry-run coverage，使每个 remove command 都证明 dry-run output 不会改变 DB rows、context/token files、project/source/workspace/worktree trees、inspection checkouts 和 trash state。
- 用同样的 fresh per-command/variant snapshots 收紧混合 `--dry-run` 加 `--force/--confirm` conflict coverage。
- 用 fresh per-command snapshots 收紧 lifecycle 和 dependency blocker matrices，其中 dependency blockers 还检查 source Git refs 不变。
- 增加 tree snapshot helper，同时记录 root 是否存在和内容，因此 empty trash directory 的创建或删除也可被观察到。
- 同步英文和中文 test specs，记录 per-command hard-remove snapshot requirements。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_force_confirm_commands_reject_incomplete_confirmation_without_side_effects tests/test_cli_contract.py::test_hard_remove_dry_runs_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Explicit Credential Surface Preflight Snapshot Hardening

已实现：

- 收紧 explicit root/admin credential-surface preflight matrix，使 root credentials 下的 token-only commands，以及 admin credentials 下的 root/token commands，都为每个 command/payload pair 建立新的 DB/file/tree snapshots。
- 该 matrix 现在会直接报告 DB、watched-file、watched-tree、touched-path 和 touched-parent preservation failures。
- 通过 per-invocation monkeypatch context 隔离 `--key-stdin` variants。
- 同步英文和中文 test specs，记录 explicit credential surfaces 的 fresh per-command/payload snapshot requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_explicit_credentials_unavailable_commands_preflight_before_handler_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Command Option Matrix Snapshot Hardening

已实现：

- 收紧 registered singleton duplicate-option matrix，使每个 command/option case 都会在 invocation 前建立新的 DB、watched-file、watched-tree、export-path 和 worktree-path snapshots。
- 用 fresh per-command/option snapshots 收紧 registered missing-value 与 structural-empty value-option matrix，覆盖 absent-value 和 empty-string cases。
- 用 fresh per-command/option/value snapshots 收紧 typed/structured malformed value matrix，覆盖 pagination、limits、choices、object ids、hashes、RFC 3339 timestamps 和 selector filters。
- 用 fresh per-case snapshots 收紧 project config/env/secret dry-run/skip-baseline conflict coverage，以及 documented non-remove conflict coverage。
- 同步英文和中文 test specs，记录 fresh per-case command-option 和 conflict snapshot requirements。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_registered_singleton_options_reject_duplicates_without_side_effects tests/test_cli_contract.py::test_registered_command_value_options_reject_missing_values_without_side_effects tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads tests/test_cli_contract.py::test_non_remove_documented_conflicts_fail_without_side_effects -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Real Dockerfile Runner Coverage

已实现：

- 为 plain Docker runner 的 Dockerfile path 增加 opt-in real Docker test，补足 image-based Docker runner coverage 之外的真实 build path。
- 该测试会从生成的 build context 构建真实 Dockerfile runner image，验证 `.dockerignore` 会把 ignored file 排除在 image context 之外，验证 ALab workspace/run directory mount contract，并检查 parsed reward。
- 同一 config 会运行两次，并断言第二次命中 ALab Docker image cache，且 cache key 与 Docker tag 保持一致。
- 同步英文和中文 test specs，使 real Docker coverage 明确包含 Dockerfile runner build context and cache reuse。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_runner_dockerfile_build_context_and_cache -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 README Real Docker Coverage Sync

已实现：

- 更新 README 和 README_cn 的 opt-in Docker validation guidance，明确写入 Docker image 与 Dockerfile runners、Dockerfile build-context filtering，以及 Dockerfile runner cache reuse，同时保留 Harbor/SkyDiscover Docker coverage 说明。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests -q`
- `git diff --check`

## 2026-05-21 Real Docker Shell Mode Coverage

已实现：

- 增加 opt-in real Docker shell-mode runner test，补足既有 fake-Docker shell argv contract 之外的真实容器执行覆盖。
- 该测试通过 `runner.shell` 运行 Alpine container，验证 `/bin/sh -c` 能看到 ALab 的 container workspace/run-dir environment，从 shell 内写入 run-dir 文件，并解析 stdout reward。
- 同步 README、README_cn 以及英文/中文 test specs，使 real Docker coverage 明确包含 Docker image command and shell execution。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_runner_shell_mode_uses_container_sh -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Real Docker Environment Isolation Coverage

已实现：

- 为 Docker image runner 增加 opt-in real Docker environment-boundary test。
- 扩展 default fake-Docker environment contract test 和 opt-in real Docker test，使二者都覆盖完整 internal operation env set。
- 这些测试证明 Docker runners 不会继承 host-only environment variables 或 host `ALAB_*` credentials，同时 internal ALab operation variables 会覆盖冲突的 `[env]` values。
- 同一批测试还验证 explicit project/experiment/run/config-version/workspace/run-dir injection、user-visible non-secret env injection、secret env injection、reward parsing，以及 captured stdout 中不渲染 secret。
- 同步 README 和 README_cn 的 opt-in Docker guidance，记录 real Docker gate 覆盖 internal `ALAB_*` override precedence。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_runner_env_is_hostless_and_internal_env_wins tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_runner_env_is_hostless_and_internal_env_overrides_config_env -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_local.py tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py tests/test_runner_docker.py tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py tests/test_runner_local.py tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py tests/test_runner_docker.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Python Environment Boundary Coverage

已实现：

- 增加 default-suite SkyDiscover Python evaluator-wrapper coverage，覆盖 V1 runner environment boundary。
- 该测试证明 host-only environment variables 和 host `ALAB_*` credentials 会被剥离，internal ALab operation variables 会覆盖冲突的 `[env]` values，并且 evaluator 可见的 `ALAB_WORKSPACE`/`ALAB_RUN_DIR` 指向 local runner workspace/run directory。
- 同一测试还验证 user env injection、secret env injection、hidden evaluator stdout capture，以及 hidden stdout 中 exact secret redaction。
- 同步英文和中文 test specs，记录 SkyDiscover Python environment-boundary coverage requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_python_runner_env_boundary_and_redaction tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Docker Environment Boundary Coverage

已实现：

- 扩展 default fake-Docker SkyDiscover Docker evaluator test，使它覆盖完整 Docker-backed runner environment boundary。
- 该测试现在证明 evaluator run 会收到 hidden bundle mount、workspace/program/run-dir container paths、explicit project/experiment/run/config-version env、user env 和 secret env，同时 host-only variables 与 host `ALAB_*` credentials 不会进入 Docker `--env` set。
- 它也验证 `ALAB_PROGRAM_PATH` 等 internal adapter env values 会覆盖冲突的 `[env]` values，并且 hidden evaluator stderr 会 redact secret values。
- 同步英文和中文 test specs，记录 SkyDiscover Docker environment-boundary coverage requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_docker_runner_builds_hidden_bundle_and_parses_metrics tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py`
- `git diff --check`

## 2026-05-21 Harbor Shared Verifier Environment Boundary Coverage

已实现：

- 扩展 default fake-Docker Harbor shared-verifier test，使它覆盖完整 Docker-backed runner environment boundary。
- 该测试现在验证 host-only variables 和 host `ALAB_*` credentials 不会进入 Docker `--env`，internal ALab operation variables 和 `ALAB_HARBOR_TASK_DIR` 会覆盖冲突的 `[env]` values，并且 Harbor task env 与 external secret env values 都会注入。
- 它还验证 hidden verifier logs 会 redact Harbor task literal env secrets 和 caller-provided secret env values。
- 同步英文和中文 test specs，记录 Harbor fake-Docker environment-boundary coverage requirement。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py::test_harbor_shared_verifier_runs_with_hidden_logs_and_secret_redaction tests/test_runner_harbor.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_harbor.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_harbor.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Python Sandbox Summary Coverage

已实现：

- 在 root/admin project summaries 和 project config summaries 中增加稳定的 `sandbox` 字段。
- SkyDiscover Python configs 现在渲染 `sandbox: not-os-sandbox`；其他 runner types 渲染 `sandbox: not-declared`，在保持输出形状稳定的同时明确 Python evaluator 的 non-OS-sandbox boundary。
- 扩展 SkyDiscover Python smoke coverage，断言 `project show` 和 `project config show` 都会渲染 non-OS-sandbox summary。
- 同步英文和中文 CLI specs，记录新的 `sandbox` field 和 rule。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_cli_contract.py::test_project_read_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_config_show_export_never_render_raw_secret_values -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_registered_commands_have_success_field_contracts_in_cli_specs tests/test_cli_contract.py::test_project_read_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_config_show_export_never_render_raw_secret_values tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_smoke.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/services.py tests/test_smoke.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Visible Output Hidden-Asset Guard Coverage

已实现：

- 收紧 default SkyDiscover Docker 和 Python runner tests，使 visible stdout 明确验证 hidden-asset 和 path non-disclosure。
- Docker evaluator test 现在证明 visible output 不包含 evaluator source paths、hidden bundle paths、hidden test data 或 private evaluator stderr text，同时 hidden logs 仍捕获 evaluator output。
- Python evaluator test 现在证明 visible output 不包含 evaluator source paths、staging paths、evaluator file names 或 private evaluator stdout，同时 hidden logs 仍捕获 evaluator output。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_real_skydiscover_python.py tests/test_real_skydiscover_catalog.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py`
- `git diff --check`

## 2026-05-21 Docker Setup Output Hidden-Log Coverage

已实现：

- Generic Docker runner 的 image pull/build/inspect setup output 现在会保留到 `hidden_stdout`/`hidden_stderr`，按 configured secret bytes redaction，并且不会进入 user-visible runner stdout/stderr。
- Docker setup failure 现在返回稳定的可见 failure reason，例如 `docker build failed`，原始 setup diagnostics 只保留在 hidden logs。
- 增加 default fake-Docker 覆盖，验证 hidden setup output、hidden validation-log persistence、redaction、`DOCKER_SETUP_OUTPUT_CAPTURED`、image auto-pull、Docker default-network argument shape，以及 Dockerfile cache key 忽略 run-time fields 但会随 build inputs 改变。
- 修正 opt-in real Docker test assertion，改用当前的 `warning_codes` result field。
- 同步 English 和 Chinese runner/test specs 中的 hidden setup-output behavior。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_project_init_persists_docker_setup_output_as_hidden_validation_logs tests/test_runner_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py tests/test_runner_docker.py tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py tests/test_runner_docker.py tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Real Adapter Docker Environment Boundary Coverage

已实现：

- 扩展 opt-in real Docker Harbor shared-verifier test，使真实 verifier container 现在检查 host-only variables 和 host `ALAB_*` credentials 不会进入容器，internal ALab operation variables 会覆盖冲突的 `[env]` values，并且 Harbor task env 和 caller secret env values 都会注入。
- 同一 Harbor 路径现在会在真实容器内输出 task/caller secret values，并验证 hidden verifier logs 会 redact 两者的 exact bytes。
- 扩展 opt-in real SkyDiscover Docker evaluator test，使真实 evaluator container 现在检查 hostless env behavior、internal `ALAB_*` 和 `ALAB_PROGRAM_PATH` override precedence、user env injection，以及 initial/cache-hit 两次执行中的 secret env injection。
- SkyDiscover Docker real-container 路径现在会把 secret 输出到 evaluator stderr，并验证 visible summaries 不包含 secret，hidden stderr 只保存 redacted value。
- 更新 README/README_cn 和 English/Chinese test specs，使 opt-in Docker validation 明确覆盖这些 adapter environment-boundary checks。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_real_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_real_docker.py`
- `git diff --check`

## 2026-05-21 Same-Parent Trash Fallback Integration Coverage

已实现：

- 增加 CLI-level worktree remove 覆盖，用于 cross-device trash staging fallback。
- 测试现在会在把 experiment worktree 移入 ALab home trash 时模拟 `EXDEV` failure，走真实 `exp worktree remove --force --confirm` 路径，并验证 ALab fallback 到 target parent directory 中的 `.alab-trash-<audit_id>`。
- 同一覆盖证明 output 和 audit metadata 会记录 `same_parent` trash mode 以及 sanitized label，immediate cleanup 会删除 same-parent trash directory，不留下 active trash cache row，并且 experiment row 会标记为 removed。
- 这补充了 lower-level helper test，并关闭此前 “same-parent fallback lacks filesystem-level integration coverage” 缺口。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_uses_same_parent_trash_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_trash_staging_uses_same_parent_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_uses_same_parent_trash_fallback_on_cross_device_rename tests/test_smoke.py::test_worktree_remove_stages_trash_and_records_metadata tests/test_smoke.py::test_worktree_remove_restores_staged_trash_after_transaction_failure tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Interrupted Record Observe Coverage

已实现：

- 将 stale running record 覆盖从 DB mutation checks 扩展到用户可见 observe 面。
- Smoke test 现在使用真实 complete run/validation ids，通过 `status` 中断 stale running run 和 validation，并验证 interrupted run 可通过 token-scoped `runs list --status interrupted` 可见、不会出现在 `--status running` 中、可按 failure reason 搜索，并可通过 `runs show` 稳定展示。
- 同一覆盖验证 interrupted run 在 CLI output 中正确渲染 nullable fields，包括 `exit code: none`、`reward: none`、`reward parse status: not_attempted`、非空 `ended at`，以及 `hidden log available: false`。
- 同时验证 interrupted validation 不再被当作 running blocker，可以通过 project validation lifecycle path 成功 archive。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Experiment Operation Lock Submit Expiry Coverage

已实现：

- 收紧 experiment operation-lock smoke coverage，使共享 run/submit lock 路径现在证明 `run` 和 `submit` 都会替换 expired lock。
- 测试现在覆盖 active lock 阻塞 `submit` 且不写入 submission，然后替换 expired lock，并验证最终 submission 成功。
- 增加可复用的 successful-submission field-label helper，并将已有 success assertions 切换到该 helper，使 submit output contract checks 与 failure helper 保持一致。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_stale_running_records_are_interrupted -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Oversized Artifact Skip Workflow Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖 baseline validation 和 experiment run 中的 oversized artifact capture。
- 测试现在验证 oversized artifact 会以 `status = skipped` 持久化，并保留 size metadata、没有 content hash，同时 validation 和 run 都保持 passed。
- 同一覆盖验证 skipped artifact 可通过 `artifacts list --status skipped` 观察、不会出现在 `--status captured` 中，并且因为没有捕获 blob bytes 而不能 export。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Artifact Symlink Escape Workflow Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖 resolved target 逃逸 configured artifact root 的 artifact symlink。
- 测试现在验证逃逸 run-dir symlink 会以 `status = skipped` 持久化，且没有 size 或 content hash，同时 baseline validation 和 experiment run 都保持 passed。
- 同一覆盖验证 skipped symlink artifact 不会出现在 captured-artifact listings 中，并且因为 ALab 没有捕获 artifact root 外的 target bytes 而不能 export。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Non-Passed Run Artifact Capture Workflow Coverage

已实现：

- 增加 CLI-level smoke coverage，证明 non-passed run outcomes 仍会捕获可用 run artifacts。
- 测试现在覆盖 runner failure、reward parse error 和 timeout 路径，每条路径都会在记录 non-passed outcome 前写入一个 run artifact。
- 同一覆盖验证每个 run 都渲染 `artifact count: 1`，每个 captured artifact 都可通过 `artifacts list --status captured` 观察，并且 export bytes 与生成的 artifact content 完全一致。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Archived Hidden Log Lifecycle Coverage

已实现：

- 收紧 Harbor hidden-log smoke workflow，使其覆盖 archived hidden logs，而不只覆盖 active hidden logs。
- 测试现在验证 root/admin `logs show --include-hidden` 可以安全查看 archived hidden log，同时 `logs list --include-hidden` 仍会隐藏它，除非同时提供 `--include-archived`。
- 同一覆盖验证 hidden archived log export 缺少 `--include-archived` 时失败，同时提供 `--include-hidden` 和 `--include-archived` 时成功，保持 redaction，并保留 token archive/unarchive/remove denials。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_config_source_observe_and_tags tests/test_runner_harbor.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 File Reward Limit Saved-Failure Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖 file reward parsing 复用 `artifacts.per_file_limit_bytes` 的规则。
- 测试现在验证 oversized file reward 会保存为 baseline validation failure，并记录 `reward_parse_status = invalid`、`reward.value = null` 和稳定 failure reason。
- 同一覆盖验证 valid-baseline experiment 路径会把 oversized file reward 记录为 saved run error，渲染 `REWARD_PARSE_ERROR`，持久化同样的 reward/failure metadata，并可通过 `runs list --failure-reason-query` 找到。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_local.py::test_file_reward_rejects_symlink_escape_at_parse_time tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Missing Working Directory Saved-Failure Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖 schema-valid 但在 selected source snapshot 中缺失的 source-dependent `runner.working_directory` path。
- 测试现在验证 missing working directory 会保存为 baseline validation `error`，记录 `reward_parse_status = not_attempted`、stderr preview text 和稳定 failure metadata，而不是被当作 config-shape error 拒绝。
- 同一覆盖验证 valid baseline 后，如果 experiment source 删除 configured working directory，会产生 saved run `RUNNER_ERROR`，且该 run 可通过 failure-reason filtering 找到。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_runner_local.py::test_project_config_rejects_working_directory_with_sibling_prefix tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_local.py::test_file_reward_rejects_symlink_escape_at_parse_time -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Missing File Reward Saved-Failure Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖 schema-valid 但在 selected source/run output snapshot 中缺失的 configured `reward.path`。
- 测试现在验证 missing baseline reward file 会保存为 validation `error`，记录 `reward_parse_status = invalid`、`reward.value = null` 和稳定 failure metadata。
- 同一覆盖验证 valid baseline 后，如果 experiment 不再写入 configured reward file，会产生 saved run `REWARD_PARSE_ERROR`。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values tests/test_runner_local.py::test_file_reward_rejects_symlink_escape_at_parse_time tests/test_runner_local.py::test_project_config_rejects_working_directory_with_sibling_prefix -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 SkyDiscover Primary Metric Failure Coverage

已实现：

- 增加 runner-level coverage，覆盖 SkyDiscover Python reward parsing 在缺少 `combined_score` 时的行为。
- 新 runner test 验证默认 SkyDiscover primary-metric 路径会 fallback 到 finite numeric top-level metrics 的平均值，而 custom configured primary metric 缺失时会产生 `status = error`、`reward_parse_status = missing` 和稳定 missing-metric failure reason。
- 增加 CLI-level smoke coverage，证明 missing custom SkyDiscover primary metric 会保存为 baseline validation failure，并持久化 metrics、`reward.value = null`、可见 safe metric names 和稳定 failure metadata。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_python_reward_fallback_and_missing_custom_primary_metric tests/test_smoke.py::test_skydiscover_python_missing_primary_metric_is_saved_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_missing_primary_metric_is_saved_failure tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_skydiscover.py`
- `git diff --check`

## 2026-05-21 Stdout Regex Truncation Saved-Failure Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖读取 redacted、truncated stdout 的 `stdout_regex` reward。
- 测试现在验证 reward text 超出 `logs.stdout_limit_bytes` 的 baseline validation 会保存为 invalid project，并记录 `reward_parse_status = missing`、`reward.value = null`、稳定 missing-reward failure reason 和 truncated stdout log record。
- 同一覆盖验证 valid-baseline experiment 后，如果 reward text 移到 stored stdout limit 之后，会产生 saved run `REWARD_PARSE_ERROR`，保留 truncated preview，并可通过 `runs list --failure-reason-query` 找到。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure tests/test_runner_local.py::test_stdout_regex_reward_uses_redacted_and_truncated_stdout tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Missing Dockerfile/Context Saved-Failure Coverage

已实现：

- 增加 Docker runner 的 CLI-level coverage，覆盖 schema-valid 但在 selected source snapshot 中缺失的 source-dependent Dockerfile 和 build-context paths。
- 新测试验证 missing baseline `runner.dockerfile` 会保存为 invalid project validation，并记录 `status = error`、`reward_parse_status = not_attempted`、稳定 runner failure reason 和持久化 stderr log record。
- 同一覆盖验证 valid-baseline experiment 后，如果移除 configured Docker build context，会产生 saved run `RUNNER_ERROR`，且 missing-path failure 本身不需要真实 Docker。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error tests/test_runner_docker.py::test_docker_config_paths_must_stay_inside_workspace tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py`
- `git diff --check`

## 2026-05-21 Nonzero Reward-Parse Failure Coverage

已实现：

- 收紧 non-passed run artifact coverage，补上 runner 非零退出且 reward parsing 同时失败的 reward-status 边界。
- 测试现在验证该路径保持 `run status = failed`，记录 `reward_parse_status = invalid`，用户可见 failure 仍为带原始 exit code 的 `RUNNER_FAILED`，并在 `record_json` 中持久化 `reward.value = null`。
- 同一 workflow 继续证明 failed、reward-parse-error 和 timed-out runs 在 runtime directories 仍可用时都会进行 best-effort artifact capture。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Artifact Directory Glob CLI Coverage

已实现：

- 增加 CLI-level smoke coverage，覆盖 artifact directory glob expansion、unprefixed workspace-root glob capture、stable path sorting 和 overlapping artifact globs 的 duplicate suppression。
- 测试现在验证 baseline validation artifacts 由 explicit file globs 加 containing directory glob 产生时，每个文件只生成一条 captured row，不产生重复 row，并在按 path 排序时使用 normalized path order 渲染。
- 同一覆盖验证同样 glob shape 的 run artifacts 会为 `run` 和默认 `workspace` roots 持久化 captured rows，报告正确 artifact count，并可精确导出 captured bytes。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_directory_globs_expand_sort_deduplicate_and_export -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_directory_globs_expand_sort_deduplicate_and_export tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates tests/test_smoke.py::test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Log Redaction Before Truncation Coverage

已实现：

- 增加 CLI-level smoke coverage，证明 secret redaction 发生在 stdout/stderr truncation 与 storage 之前。
- 测试使用一个如果先 truncation 就会泄露 partial secret 的 log byte limit，然后验证 baseline validation stdout/stderr logs 保存 `prefix [REDACTED]`，标记 `truncated = true`，且不包含 raw 或 partial secret text。
- 同一覆盖验证 saved run previews 和 run log records 保持同样的先 redaction 后 truncation 行为，并证明 log `stored_bytes`、`content_hash` 与 exported byte files 都匹配精确存储的 redacted prefix。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Global Preview Bytes Log Coverage

已实现：

- 将 `output.preview_bytes` 接入 validation 与 experiment run 的 log storage，使保存的 stdout/stderr previews 不再使用 hard-coded 4096-byte prefix。
- 同一 preview limit 现在一致应用到 validation 与 run capture paths 创建的 visible 和 hidden log streams。
- 增加 CLI-level smoke coverage，证明非默认 global preview length 会反映在 baseline validation log list output、saved experiment run previews、run log list output 与持久化 `log_streams.preview_text` metadata 中，同时不会截断实际存储的 log bytes。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_global_preview_bytes_controls_validation_and_run_log_previews -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_global_preview_bytes_controls_validation_and_run_log_previews tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py src/alab/services.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py src/alab/services.py tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Logs Show Full Content Coverage

已实现：

- 将 `observe logs show` rendering 与轻量 log list/export metadata 分离，使 `show` 现在会读取 stored log byte file，并渲染 safe UTF-8 replacement-decoded full log `content`。
- 保留既有 `logs list` 和 `logs export` field shapes，同时把 `logs show` 明确记录为 runner spec 所承诺的 full-content CLI surface。
- 扩展 smoke 与 CLI-contract coverage，覆盖 active visible logs、archived visible logs、root/admin 搭配 `--include-hidden` show hidden logs，以及 top-level `logs show` aliases 都会渲染 documented `content` field，且不会暴露已 redacted 的 hidden-log secrets。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_cli_contract.py::test_observe_read_aliases_render_equivalent_outputs tests/test_cli_contract.py::test_observe_lifecycle_aliases_render_canonical_shapes -q`

## 2026-05-21 Progress Dashboard Consolidation

已实现：

- 增加 top-level current snapshot，使后续读者不用通读完整 dated journal 就能看到实际 V1 implementation state。
- 增加 authoritative active backlog，并按 P0 completion blockers、P1 release hardening 和 P2 maintenance 拆分；同时明确旧的历史 `尚未完成` 条目不再是 authoritative，除非被提升到 active backlog。
- 增加 next-best-batch guidance 和 progress-file maintenance rules，使后续更新能保持 dashboard current，同时把详细 implementation log 保留为 evidence。

验证：

- `git diff --check`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_registered_command_success_field_contracts_are_synchronized tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`

## 2026-05-21 Empty Ambient Credential Contract Coverage

已实现：

- 为 `docs/spec_tests.md` 要求的 `ALAB_KEY=""` ambient environment case 增加 focused CLI-contract coverage。
- 测试证明 empty ambient key 对 project-context repair 的行为与 absent credential 完全一致：`AUTH_REQUIRED`、exit `3`、稳定 error rendering、stderr 与 absent-key case 一致，并且没有 SQLite side effects。
- 更新 progress dashboard 的 recent-batch 与 next-batch summaries，使文件顶部继续展示 actionable current state。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_empty_ambient_alab_key_behaves_like_absent_credential tests/test_cli_contract.py::test_key_stdin_input_validation_is_strict_global_contract tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Completion Audit Evidence Matrix

已实现：

- 新增 `docs/completion_audit.md` 作为 active V1 requirement-to-evidence ledger，与本 chronological progress log 分离。
- 新增同步的 `docs/completion_audit_cn.md`，使新 audit artifact 符合项目 English-first 加 Chinese-pair documentation rule。
- 用 P0 completion gates 以及 CLI contracts、storage/auth/context、project/source/experiment/observe collaboration、runner/adapter coverage 的 grouped evidence rows 初始化矩阵。
- 明确将剩余证明工作标为 `PARTIAL`、`PENDING` 或 `ENV-GATED`，避免把 grouped evidence 当作 completion proof。
- 更新 progress dashboard，使 audit ledger 成为下一步 P0 入口。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Observe Unarchive Idempotency Coverage

已实现：

- 强化 run、artifact 和 log unarchive idempotency 的 lifecycle smoke coverage。
- Repeated unarchive 现在会验证稳定 field labels、不变的 `unarchived at` timestamps、`audit id: none`，以及不会产生重复 unarchive audit rows。
- 在 idempotency checks 后重新 archive 这些对象，使既有 hard-remove 和 reference-counted trash coverage 继续经过 archived path。
- 更新 `docs/completion_audit.md` 与 `docs/completion_audit_cn.md` 记录更强证据，同时在每个 lifecycle command 完成 row-by-row audit 前，仍保持 lifecycle row 为 `PARTIAL`。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Lifecycle Evidence Row Audit

已实现：

- 将 `docs/completion_audit.md` 的 lifecycle section 扩展为 per-object evidence table，覆盖 project、source、validation、experiment、run、artifact、log、annotation、worktree 和 inspection checkout lifecycle surfaces。
- 将 archive/unarchive idempotency evidence 与 remove/dry-run/blocker evidence 分开映射，使后续 audit 能直接看到哪些 tests 证明哪些 lifecycle rule。
- 在 full default suite 重新运行并且 broader requirement-level audit 完成前，仍保持 grouped lifecycle row 为 `PARTIAL`；同时将每个 object-family row 标为 proved pending that full-suite rerun。
- 同步更新 `docs/completion_audit_cn.md` 的中文 evidence mapping。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_hard_remove_dry_runs_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Default Suite Verification

已实现：

- 在 lifecycle/audit consolidation batch 后运行完整 default pytest suite；default opt-in real-environment tests 按 marker 预期 skipped。
- 在 full pytest run 后，运行 repository-wide `ruff`、`compileall` 和 whitespace checks。
- 更新 `docs/completion_audit.md` 与 `docs/completion_audit_cn.md`，使 default-suite P0 gate 记录已通过的 command set，同时仍要求 future changes 后重新运行。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Project Source Experiment Audit Expansion

已实现：

- 在 `docs/completion_audit.md` 中扩展 `docs/spec_project_source_experiment.md` 高风险部分的 requirement-level evidence rows。
- 增加 project config schema、runtime baseline/config edit semantics、config read/export secret-retain behavior、project init precedence、source import/model behavior、public inline source import、experiment creation/visibility/mutable scope，以及 run/submit lifecycle rows。
- 只有当前 default-suite evidence 足够直接时才标为 `PROVED`；如果剩余工作是 row-level mapping 或具体 missing evidence check，则继续保持 broader rows 为 `PARTIAL`。
- 同步更新 `docs/completion_audit_cn.md` 的中文 audit expansion。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Storage Auth Context Audit Expansion

已实现：

- 在 `docs/completion_audit.md` 中扩展 `docs/spec_storage_auth_context.md` 高风险部分的 requirement-level evidence rows。
- 增加 home/init behavior、SQLite connection and DDL contracts、migration and backup policy、canonical JSON shapes、credential/token behavior、secret handling、global config、context marker/path registry behavior、capability resolver preflight、context repair、locks/stale cleanup，以及 audit retention/sanitization rows。
- 只有已经具备 assertion-level default-suite evidence 的范围才标为 `PROVED`；更宽的范围继续保持 `PARTIAL`，并写明具体 remaining audit tasks，例如 home-id entropy evidence、old-experiment secret binding、conflicted-marker variants、inspection self-repair pinned-commit checks 和 per-object audit metadata review。
- 同步更新 `docs/completion_audit_cn.md` 的中文 audit expansion。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Observe Collaboration Audit Expansion

已实现：

- 在 `docs/completion_audit.md` 中扩展 `docs/spec_observe_collaboration.md` 的 requirement-level evidence rows。
- 增加 visibility policy 与 token/inspection intersection、observe command and alias surfaces、search corpus privacy、pagination/filter/sort contracts、best ranking、run/log access、artifact export、tags、annotation targets and revisions，以及 public safe status rows。
- 当前 tests 很强但还未穷尽的宽范围继续保持 `PARTIAL`，并写明具体 remaining actions，例如 regenerated-token visibility matrices、每个 sort whitelist、`best` tie ordering、hidden-log archived export branches、hidden-asset artifact exclusion、annotation dirty-worktree variants 和 public safe-status negative fields。
- 同步更新 `docs/completion_audit_cn.md` 的中文 audit expansion。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Runner Adapter Audit Expansion

已实现：

- 在 `docs/completion_audit.md` 中扩展 `docs/spec_runners_adapters.md` 的 requirement-level evidence rows。
- 增加 shared runner contracts、config path/schema validation、local runner behavior、Docker runner/cache/capability behavior、reward extraction、artifact capture、logs/hidden logs、Harbor adapter contracts、SkyDiscover catalog/source/evaluator behavior，以及 real-environment validation gates rows。
- 将 default fake/local proof 与 `ENV-GATED` real Docker、live SkyDiscover catalog、network dependency、native dependency validation 分开记录，避免 future completion claims 夸大 fake-adapter evidence。
- 同步更新 `docs/completion_audit_cn.md` 的中文 audit expansion。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 CLI Long Tail Audit Expansion

已实现：

- 在 `docs/completion_audit.md` 中增加 dedicated CLI long-tail evidence table，来源为 `docs/spec_cli.md` 和 `docs/spec_tests.md` 的 golden CLI section。
- 将剩余 CLI 工作拆成 parser、positional selector、renderer、success-schema、saved result-failure、system-error/debug、error/warning matrix、capability preflight、file-payload 和 repository documentation contract rows。
- 当前 generated/current tests 证据直接的 parser 和 renderer foundations 标为 `PROVED`；已知仍需补证据的 rows 保持 `PARTIAL`：Git SHA selector abbreviation/ambiguity、conditional alias success variants、saved failure breadth、exhaustive error matrices、capability payload variants 和 invalid file-payload cases。
- 更新 progress dashboard，使剩余 P0 backlog 指向 blueprint-level product invariants 和具体 `PARTIAL` rows，而不是笼统的 “CLI long-tail” bucket。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Blueprint Product Invariants Audit Expansion

已实现：

- 在 `docs/completion_audit.md` 中增加 blueprint-level product invariants table，使 completion ledger 直接覆盖 `docs/blueprint.md`，而不只围绕 subsystem specs。
- 增加 local-only product scope、core workflow、object model、plaintext/security boundaries、runtime stack and architecture、ALab home layout、CLI/output contract、source/public experiment direction、lifecycle direction、runner/adapter direction、documentation discipline 和 host/release gates rows。
- 对 absence-of-feature 和 release-environment-dependent rows 继续保持 `PARTIAL` 或 `ENV-GATED`，避免从宽泛 implementation shape 过度声称已证明。
- 更新 progress dashboard，使下一步工作转为把高风险 `PARTIAL` rows 转成 tests 或 exact evidence references。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Runtime Surface Contract Guard

已实现：

- 新增 `tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies`。
- 该测试读取 `pyproject.toml` runtime dependencies，并解析 `src/alab/*.py` imports，拒绝 V1 blueprint 明确排除的 server/web UI frameworks、ORMs、scheduler/agent-loop packages 和 LLM-provider SDKs。
- 更新 `docs/completion_audit.md` 与 `docs/completion_audit_cn.md`，使 blueprint product-scope 和 runtime-stack rows 引用这条新的 absence-of-feature guard。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`

## 2026-05-21 ALab Home Layout Contract Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint`。
- 测试覆盖 `HOME` 下默认 `~/.ALab` resolution、`ALAB_HOME`、explicit `--home` precedence、canonical home directories、无 `records/` directory、database `home_id` persistence、project marker `home_id`、marker-only project control contexts，以及 cwd-relative default experiment worktree marker propagation。
- 修复 project initialization，使其通过 `src/alab/services.py::_ensure_project_artifact_layout` 在初始化时立即创建 canonical `projects/<project_id>/artifacts/blobs` 和 `projects/<project_id>/artifacts/logs` directories，对齐 blueprint layout，即使尚未发生 artifact/log capture。
- 同步更新英文和中文 completion audit 的 home/layout rows，记录新的 focused evidence。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_cli_contract.py`

## 2026-05-21 Progress Dashboard Log Split

已实现：

- 将当前 progress dashboard 与历史 implementation journal 拆分。`docs/progress.md` 现在是简短的 current-status/backlog/next-batch dashboard，`docs/progress_log.md` 保存完整 dated implementation journal。
- 新增同步的 `docs/progress_log_cn.md`，并将 `docs/progress_cn.md` 缩减为对应 dashboard。
- 更新 README、completion audit 和本地 AGENTS guidance，使后续 agent 先读短 dashboard，只在需要历史证据时查看日志。
- 将 full default-suite completion gate 标为对当前 worktree 已 stale，因为上次 full-suite 通过后又落地了 implementation 和 documentation changes。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `git diff --check`

## 2026-05-21 Experiment-Bound Secret Coverage

已实现：

- 新增 `tests/test_smoke.py::test_experiment_runs_keep_bound_secret_after_project_secret_change`。
- 测试先用初始 `secret_env` 值在 config version 1 下创建 experiment，再修改 project secret 生成新的 active config version；随后证明既有 experiment 仍使用 config version 1 和原始 secret，而新建 experiment 绑定新的 config/secret。
- Runner 只比较 secret hash 并写入数字 reward，因此 CLI output 不包含 raw secret value，同时仍能证明 bound-secret behavior。
- 更新 completion audit 和 progress dashboard，将该项从 active high-risk proof gaps 中移除。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_secret_input_contract tests/test_smoke.py::test_experiment_runs_keep_bound_secret_after_project_secret_change tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 CLI Text File Payload Edge Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_text_file_payloads_reject_bad_files_without_side_effects`。
- 测试覆盖 `project init --config`、`project config import --config`、`project secret set --value-file`、`submit --summary-file`、`submit --feedback-file`、`annotate add --body-file` 和 `annotate edit --body-file`，输入包括 invalid UTF-8 files、把 directory 当作 file，以及在平台会执行 file permission 的情况下的 unreadable files。
- 它验证每个 payload failure 都得到稳定 `CONFIG_INVALID` error block、无 stdout、无 SQLite writes，并且 watched filesystem 不变化。
- 修复 `src/alab/configs.py::load_project_config`，使目录、invalid UTF-8 和 unreadable project config files 映射为 `CONFIG_INVALID`，不再逃逸为 system errors。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_text_file_payloads_reject_bad_files_without_side_effects tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/configs.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/configs.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Git Commit SHA Selector Disambiguation

已实现：

- 在 `src/alab/services.py::_resolve_commit_sha_selector` 中新增 Git object disambiguation，用于 commit SHA selectors。
- `latest`、`final`、`best` 以及 full/unambiguous SHA selectors 仍会解析为 concrete commits；ambiguous SHA prefixes 现在会稳定返回 `CONFIG_INVALID`，不再依赖 raw Git diagnostics。
- 新增 `tests/test_cli_contract.py::test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity`。
- 该测试覆盖 `exp create --from-commit`、`exp checkout --commit` 和 annotation path/line targets 接受 abbreviated SHA；同时覆盖 experiment creation、inspection checkout 和 annotation creation 在 ambiguity rejection 时没有 DB 或 filesystem side effects。
- 更新 completion audit 和 progress dashboard，将 Git SHA selector abbreviation/ambiguity 从 active high-risk CLI proof gaps 中移除。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity tests/test_cli_contract.py::test_alab_object_selectors_require_complete_ids tests/test_cli_contract.py::test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_experiment_checkout_success_fields_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/services.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/services.py tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Public Safe Status Negative-Field Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields`。
- 该测试创建包含 project history、experiment/run/annotation records、env values、`secret_env` names and values、runner-command/log/artifact markers、hidden log and hidden-asset rows、absolute catalog/cache paths、adapter staging path markers 和 failed-baseline log markers 的 public-status fixtures。
- 它验证 no-key valid public status 保持 documented public shape，no-key invalid public status 保持缩减的 public-invalid shape，并且两种输出都不包含任何 forbidden private/runtime fragments。
- 更新 completion audit 和 progress dashboard，使 public safe status row 现在拥有直接 negative-field evidence。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields tests/test_cli_contract.py::test_status_object_type_tracks_context_mode tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Regenerated Token Private Annotation Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights`。
- 该测试先在 worktree token context 中创建 experiment-private annotation，再通过 admin command 重新生成该 worktree token，然后证明原始 raw token 被 revoke 后，同一个 experiment context 仍然能 show 和 edit 这个 private annotation。
- 它验证 context marker 切换到 new token id、old token row 已 revoked、new token row 为 active、raw token value 已变化，并且 annotation revision creator metadata 仍然绑定 experiment，而不是绑定 raw token。
- 更新 completion audit 和 progress dashboard，将 regenerated-token private annotation visibility/editing 从 active high-risk proof gaps 中移除，同时保持更广泛的 visibility matrix rows 为 `PARTIAL`。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Admin Private-To-Exp Annotation Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit`。
- 该测试用 admin credential 创建 private annotation：target 指向一个 experiment，同时通过 `--private-to-exp` 将 visibility 绑定到另一个 experiment。
- 它证明 target experiment token 不能 show、edit 或 archive 该 private annotation，而 selected creator experiment token 可以 show、edit、archive 和 remove。
- 它验证 stored `visibility_json`、annotation creator metadata、revision creator metadata、final row deletion、dry-run/final `deleted revisions`，以及 remove audit 的 `deleted_revision_count`/filesystem metadata。
- 更新 completion audit 和 progress dashboard，使 admin `--private-to-exp` 与这条 private remove-audit path 不再是 stale proof gaps，同时更广泛的 annotation authorization matrices 仍保持 `PARTIAL`。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Runner Operation Cleanup Coverage

已实现：

- 扩展 local、Docker、Harbor、SkyDiscover Python 和 SkyDiscover Docker focused tests，增加 service-level operation cleanup assertions。
- `tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed` 现在会向 runner temp workspace/run directories 写入 marker files，然后证明 validation 和 run operation directories 已删除，visible experiment worktree 保持未修改。
- Harbor 与 SkyDiscover smoke tests 现在断言 capture 后 validation/run temp dirs 已消失，并且 runner execution 让 experiment worktree 保持 visibly clean。
- `tests/test_runner_docker.py::test_project_init_persists_docker_setup_output_as_hidden_validation_logs` 现在覆盖 fake-Docker validation 和 fake-Docker experiment run 的 cleanup/worktree immutability。
- 更新 completion audit 和 progress dashboard，将 default-path runner temp-dir cleanup 从 active high-risk proof gaps 中移除，同时继续把 real-environment runner confirmation 单独保留。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_runner_docker.py::test_project_init_persists_docker_setup_output_as_hidden_validation_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_docker.py`
- `git diff --check`

## 2026-05-21 Home Id And Tag Edge Coverage

已实现：

- 扩展 `tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint`，增加 home-id suffix checks，覆盖 V1 22-character unpadded base64url shape 且可解码为 16 bytes。
- 扩展 `tests/test_smoke.py::test_capability_help_and_preflight_surfaces`，让 inspection checkout 直接尝试 `exp tag add` 并收到 `COMMAND_UNAVAILABLE`。
- 扩展 `tests/test_smoke.py::test_config_source_observe_and_tags`，在添加 `baseline` 后再添加 `BASELINE`，从 rendered output 和 SQLite rows 两层证明 lowercase slug normalization 与 duplicate-tag idempotency。
- 更新 completion audit 和 progress dashboard，使 home-id entropy 不再是 active high-risk backlog item；tags row 只保留剩余 visibility-expansion proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint tests/test_smoke.py::test_capability_help_and_preflight_surfaces tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_smoke.py`

## 2026-05-21 Tag Authorization No-Expansion Coverage

已实现：

- 扩展 `tests/test_smoke.py::test_config_source_observe_and_tags`，增加直接 root tag-add 和 admin tag-remove assertions，同时保留已有 owning-token tag flow 和 duplicate normalized tag coverage。
- 扩展 `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`，先将 project visibility 收窄为 `none`，再通过 worktree token 和 inspection token 的 same-tag experiment lists 证明 tags 只过滤 already-visible experiments，不会扩展 authorization。
- 更新 completion audit，将 Tags row 标为 default token/admin/root/inspection contexts 下已证明。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`

## 2026-05-21 Experiment Search Corpus Coverage

已实现：

- 扩展 `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`，为 project task text、experiment goals、tags、final summary、final feedback 和 case-insensitive matching 增加 explicit search corpus assertions。
- 保留同一测试中已有的 stdout、stderr、artifact bytes、historical annotation revisions 和 private annotation visibility 的 negative corpus assertions，使 search corpus/privacy audit row 在一条 focused path 中获得直接证据。
- 更新 completion audit 和 progress dashboard，将 default local experiment search corpus/privacy surface 标为已证明。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`

## 2026-05-21 Experiment Best Ranking Coverage

已实现：

- 扩展 `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`，在已有 search/visibility 路径后增加 direct best-ranking assertions。
- 增加受控 tie experiments 与 synthetic run rows，证明同一 experiment 多个 runs qualify 时只输出一个 block、同一 experiment 内选择最新 qualifying run、按 ended time 再按 experiment id 的 tie ordering，以及排除高 reward 的 `running`/`failed`/`error`/`timeout`/`interrupted` 和 unparsed passed runs。
- 更新 completion audit 和 progress dashboard，将 default local experiment best surface 标为已证明，同时保留 broader completion 与 full-suite gates。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`

## 2026-05-21 Progress Dashboard Pipeline Split

已实现：

- 将 `docs/progress.md` 缩减为短 dashboard，只覆盖 current position、completion gates、recently closed gaps，以及指向下一步工作文件的入口。
- 新增 `docs/progress_pipeline.md` 作为 authoritative active queue，包含明确的 operating rules、active batches、closed evidence gaps、full-suite policy 和 update checklist。
- 新增同步中文 dashboard/pipeline 文件，并更新 README 与 completion-audit 指针，避免后续 agent 把历史日志当成 backlog。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing -q`
- `git diff --check`
- `rg -n "[ \t]+$" README.md README_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 Annotation Authorization Matrix Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations`。
- 该测试证明 project-visible peer annotations 可被 target experiment token 读取，但不能被它 edit/archive/unarchive/remove，包括 creator archive 之后的 archived 状态。
- 它证明 archived annotations 默认 list 隐藏，但仍可通过 id show 和 `--include-archived` 查看，同时 archived status 不会授予 lifecycle mutation rights。
- 它证明 current project visibility 仍会 cap annotation visibility，private peer annotations 对 target experiment 保持隐藏，并且 inspection contexts 可以读取可见 annotations，但不能执行 `annotate add/edit/archive/unarchive/remove`。
- 更新 completion audit 和 progress pipeline，使 annotation visibility/lifecycle row 不再是 active P0 proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Optional Warning Output Closure

已实现：

- 新增 `tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry`。
- 该测试证明 ALab-owned Docker image prune 失败时会渲染带 `DOCKER_CACHE_PRUNE_FAILED` 的 `object: warning` block，保持 cache entry 为 active，并在 audit metadata 中记录 warning count。
- 更新 completion audit 和 progress pipeline，使 optional warning outputs 不再是 active CLI long-tail gap。剩余 CLI 焦点是 saved-result tails、less-used aliases，以及 command-specific `SCOPE_VIOLATION`/archived/config/output/lifecycle blocker matrices。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_cli_contract.py::test_source_import_warning_success_fields_follow_cli_spec tests/test_cli_contract.py::test_context_token_file_permission_warning_renders_after_primary_result tests/test_cli_contract.py::test_warning_code_catalogs_cover_implemented_warning_codes tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Run Reward Parse Failure Matrix Coverage

已实现：

- 新增 `tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit`。
- 该测试证明 file rewards 包含 `NaN`、`Infinity`、empty strings 和 non-numeric text 时，run-level saved result failures 会稳定渲染并持久化。
- 它还证明 nonzero-exit plus invalid reward case 会保持 run status `failed`，渲染 `RUNNER_FAILED`，并存储 invalid reward parse status，而不会覆盖 runner failure reason。
- 更新 completion audit 和 progress pipeline，使 local reward-parse variants 不再作为 active saved-failure proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_cli_contract.py::test_run_result_failures_follow_cli_spec tests/test_cli_contract.py::test_project_validate_result_failures_follow_cli_spec tests/test_cli_contract.py::test_submit_result_failures_follow_cli_spec tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_file_reward_read_limit_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Docker Unavailable Saved Failure Coverage

已实现：

- 扩展 `tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error`，增加精确 project-init failure field ordering 和 exit-code assertions。
- 新增 `tests/test_runner_docker.py::test_docker_unavailable_run_is_saved_result_failure`。
- 新测试先创建 valid fake-Docker project，再在 `alab run` 时让 Docker unavailable，证明 saved run result exit `1`、渲染 `RUNNER_ERROR`、存储 `status=error` 和 `reward_parse_status=not_attempted`，并将 Docker missing reason 捕获为 stderr log metadata。
- 更新 completion audit 和 progress pipeline，使 Docker-unavailable saved failures 不再是 active saved-failure proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error tests/test_runner_docker.py::test_docker_unavailable_run_is_saved_result_failure tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Python Dependency Saved Failure Coverage

已实现：

- 收紧 `tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results`。
- 该测试现在证明 fake-`uv` dependency installation failures 在 baseline validation 和 experiment run 两条路径中都保持 saved result failures、exit `1`、渲染预期 result failure fields、持久化 error records、只把 setup output 捕获到 hidden logs，并且在 `ALAB_DEBUG=1` 下不会泄露 debug traceback。
- 更新 completion audit 和 progress pipeline，使 dependency-installation saved failures 对 default/fake SkyDiscover Python path 不再是 active saved-failure proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Pipeline Focus Maintenance

已实现：

- 保持 `docs/progress.md` 作为短 dashboard，并让 `docs/progress_pipeline.md` 在顶部显式承载 current active batch。
- 更新 CLI success-schema audit row，将 public/public-invalid `status`、observe read aliases、observe lifecycle aliases 和 hidden-log default shapes 记录为已证明 evidence，而不是 remaining examples。
- 将 observe alias closure 加入 dashboard 和 pipeline 的 closed-gap lists，避免后续 batch 重复打开已经证明的 output variants。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 CLI Capability Payload Preflight Audit Narrowing

已实现：

- 收紧 `tests/test_cli_contract.py::test_object_specific_not_found_errors_stay_precise_for_root_admin_selectors`，使其断言每个有当前 runtime selector 的 documented not-found code 都被覆盖，并显式排除 `CACHE_NOT_FOUND`，因为 V1 没有 cache-id selector command。
- 更新 completion audit，将已证明的 generated payload/capability preflight variants 与仍开放的 command-error matrix work 区分开。
- 将 pipeline 的 active CLI batch 收窄为 optional warning blocks、less-used aliases，以及 command-specific `SCOPE_VIOLATION`/archived/config/output/lifecycle blocker matrices。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_object_specific_not_found_errors_stay_precise_for_root_admin_selectors tests/test_cli_contract.py::test_locked_commands_preflight_before_handler_argument_effects tests/test_cli_contract.py::test_nested_help_uses_same_locked_preflight_with_handler_payloads tests/test_cli_contract.py::test_explicit_credentials_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_project_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_experiment_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_inspection_context_unavailable_commands_preflight_before_handler_effects tests/test_cli_contract.py::test_explicit_keys_preserve_context_conflict_before_handler_effects tests/test_cli_contract.py::test_text_file_payloads_reject_bad_files_without_side_effects tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches。

## 2026-05-21 Alias Group Boundary Closure

已实现：

- 新增 `tests/test_cli_contract.py::test_registered_alias_groups_are_limited_to_covered_observe_surfaces`。
- 该测试枚举当前每个 handler-backed command alias group，证明不存在已覆盖 observe/read/lifecycle surfaces 之外的 less-used alias groups。
- 更新 completion audit 和 pipeline，使 alias work 不再是 active CLI long-tail item；剩余 CLI 焦点是 saved-result tails 和 command-specific error/blocker matrices。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_command_registry_paths_aliases_and_matcher_are_stable tests/test_cli_contract.py::test_registered_alias_groups_are_limited_to_covered_observe_surfaces tests/test_cli_contract.py::test_observe_read_aliases_render_equivalent_outputs tests/test_cli_contract.py::test_observe_lifecycle_aliases_render_canonical_shapes tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Saved Result Tail Closure

已实现：

- 新增 `tests/test_cli_contract.py::test_saved_result_failure_tails_have_stable_cli_shape`。
- 该测试固定 shared saved-result tail contract，覆盖 baseline failures、run failures、包含 `error` parse status 的 reward-parse failures，以及 submission failure blocks。
- 更新 completion audit，使 registered success schemas 和 saved result-failure rendering 对当前 local/default/fake runner surfaces 不再是 active CLI long-tail gaps。
- 更新 pipeline，使剩余 CLI long-tail 收窄为 command-specific error/blocker matrix。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_saved_result_failure_tails_have_stable_cli_shape tests/test_cli_contract.py::test_project_baseline_result_failures_follow_cli_spec tests/test_cli_contract.py::test_run_result_failures_follow_cli_spec tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_cli_contract.py::test_project_validate_result_failures_follow_cli_spec tests/test_cli_contract.py::test_submit_result_failures_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Source-Dependent Missing-Path Saved Failure Coverage

已实现：

- 扩展 `tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit`，使 submit `--rerun` 遇到 missing file reward 时会渲染为带 `REWARD_PARSE_ERROR` 的 saved submission failure，不输出 traceback，不存储 submission，并持久化 failed run record。
- 扩展 `tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors`，增加 exact baseline/run field-label assertions，并覆盖 missing Docker context 的 submit `--rerun` wrapping。
- 更新 completion audit 和 progress pipeline，使 source-dependent missing-path saved failures 对 default/fake surfaces 下的 local runner working directories、file rewards、Dockerfiles 和 Docker contexts 不再是 active saved-failure proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py tests/test_runner_docker.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py tests/test_runner_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Docker Setup Saved Failure Coverage

已实现：

- 新增 `tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures`。
- 该测试证明 Docker image pull failures 和 Dockerfile build failures 在 baseline validation 与 experiment run 两条路径中都会成为 saved result failures、exit `1`、渲染 `RUNNER_ERROR` 或 `BASELINE_VALIDATION_FAILED` result tails、持久化 `status=error` 与 `reward_parse_status=not_attempted`、visible stderr 只暴露稳定原因，并把 setup stdout/stderr 存为 hidden logs。
- 更新 completion audit 和 progress pipeline，使 Docker pull/build saved failures 对 fake/default Docker paths 不再是 active saved-failure proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error tests/test_runner_docker.py::test_docker_unavailable_run_is_saved_result_failure tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Adapter Docker Build Saved Failure Coverage

已实现：

- 新增 `tests/test_smoke.py::test_adapter_docker_build_failures_are_saved_results`。
- 该测试证明 Harbor separate-verifier Dockerfile build failures 和 SkyDiscover Docker evaluator build failures 在 baseline validation 和 experiment run 两条路径中都会成为 saved result failures。
- 它断言 rendered failure fields、持久化的 `status=error` 与 `reward_parse_status=not_attempted`、稳定 visible stderr reasons，以及 hidden setup stdout/stderr logs。
- 更新 completion audit 和 progress pipeline，使 adapter-specific Docker build/setup saved failures 对 fake/default paths 不再是 active saved-failure proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_adapter_docker_build_failures_are_saved_results -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_adapter_docker_build_failures_are_saved_results tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Dashboard/Pipeline Separation Cleanup

已实现：

- 将 `docs/progress.md` 压成真正的短 dashboard：只保留 gate states、一行 active focus 和高层 do-not-reopen summary。
- 将 detailed closed-gap list 继续只放在 `docs/progress_pipeline.md`，并增加明确维护规则：evidence 关闭时改写 stale queue rows，不追加重复 backlog。
- 同步更新中文 dashboard 和 pipeline。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Archived/Closed/Removed State Error Matrix

已实现：

- 新增 `tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem`。
- 该测试覆盖 `exp create`、`run` 和 `submit` 的 `PROJECT_ARCHIVED`，`run` 和 `submit` 的 `EXPERIMENT_CLOSED`，以及 `run` 和 `submit` 的 removed-worktree `SCOPE_VIOLATION`。
- 每个 case 都断言 stable error block、exit `4`、exact reason、`next: none`，以及无 database 或 watched filesystem mutations。
- 更新 completion audit 和 progress pipeline，使 archived/closed/removed-state experiment command errors 与 hard-remove lifecycle blockers 不再是 active CLI-row gaps。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_hard_remove_dependency_blockers_preserve_database_and_filesystem tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Export Output Error Matrix Audit Closure

已实现：

- 复查现有 export-output evidence，并更新 completion audit 和 progress pipeline，没有新增重复测试。
- `tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks` 已覆盖 project config、artifact 和 log export 的 `OUTPUT_EXISTS`、directory target rejection、overwrite success、artifact/log missing-parent preflight，以及无 database/config mutation。
- Active CLI command-error matrix 现在收窄为 remaining config-value branches 和更宽 visibility `SCOPE_VIOLATION` selectors。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md tests/test_cli_contract.py` returned no matches.

## 2026-05-21 Visibility Scope Selector Error Matrix

已实现：

- 新增 `tests/test_cli_contract.py::test_visibility_scope_selector_errors_are_non_disclosing_and_side_effect_free`。
- 该测试创建 peer experiment、run、artifact、log 和 annotation records，然后将 visibility 降为 `none`，证明 first experiment token 对每个 peer selector 都得到 stable non-disclosing `SCOPE_VIOLATION` errors。
- 每个 selector assertion 都检查 exit `4`、exact reason、没有对应的 `*_NOT_FOUND` code，并且没有 database 或 watched filesystem mutation。
- 更新 completion audit 和 progress pipeline，使更宽 visibility `SCOPE_VIOLATION` selectors 不再是 active CLI-row gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_visibility_scope_selector_errors_are_non_disclosing_and_side_effect_free tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Config-Version Error Matrix Closure

已实现：

- 新增 `tests/test_cli_contract.py::test_config_version_value_errors_preserve_database_and_filesystem`。
- 该测试覆盖没有 active config 时的 project config show/export `active-valid`、missing explicit config versions、non-numeric version selectors、没有 active config 时的 `exp best`，以及 missing config version 的 `exp best --config-version`。
- 每个 case 都断言 stable error block、exit code、exact reason、`next: none`，以及无 database、watched filesystem 或 export-output mutation。
- 更新 completion audit 和 progress pipeline，使 CLI command-error matrix 不再是 active proof gap；当前 active batch 现在是 hidden asset/log 和 adapter failure cleanup edges。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_config_version_value_errors_preserve_database_and_filesystem -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_config_version_value_errors_preserve_database_and_filesystem tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Python Non-Import Proof

已实现：

- 扩展 `tests/test_runner_skydiscover.py::test_skydiscover_python_runner_materializes_hidden_bundle_and_metrics`。
- 该测试现在通过对比 evaluator import pid 与当前进程，并断言 wrapper module 不存在于 main-process `sys.modules`，证明 evaluator module 在 wrapper subprocess 中 import，而不是在 main ALab process 中 import。
- 同一测试继续证明 hidden bundle materialization、visible `sandbox: not-os-sandbox` disclosure，以及 evaluator source/stdout/paths 不出现在 visible stdout。
- 更新 runner/adapters audit row 和 progress pipeline，使这个 SkyDiscover Python default/fake proof gap 关闭。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_python_runner_materializes_hidden_bundle_and_metrics -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_skydiscover.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_skydiscover.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_skydiscover.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Reward Parser Matrix Closure

已实现：

- 新增 `tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits`。
- 新增 `tests/test_runner_harbor.py::test_harbor_reward_parser_handles_json_text_missing_and_invalid_values`。
- 更新 Harbor `reward.json` parsing：存在但 non-numeric 或 non-finite 的 primary metric 现在归类为 `invalid`；缺失 primary metric 仍为 `missing`，与 reward parsing spec 对齐。
- 更新 runner/adapters audit row 和 progress pipeline，使 reward extraction 在 default/fake paths 上已证明，只剩 real adapter environments 属于 environment-gated。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py::test_harbor_reward_parser_handles_json_text_missing_and_invalid_values tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/runner.py tests/test_runner_harbor.py tests/test_runner_local.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Progress Log Chronology Cleanup

已实现：

- 保持 `docs/progress.md` 和 `docs/progress_cn.md` 为 46 行 dashboard，由 `docs/progress_pipeline.md` 与 `docs/progress_pipeline_cn.md` 承载 active queue 和 closed-gap guardrails。
- 将 SkyDiscover Python non-import 与 reward parser matrix closure entries 移到 config-version closure 之后的 chronological progress log 末尾，对齐真实最新 implementation 顺序。
- 将中文日志中 optional warning 与 run reward parse failure sections 的顺序对齐英文 canonical log。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 Artifact Blob Lifecycle Closure

已实现：

- 新增 `tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting`。
- 该测试让 baseline validation 与 experiment run 产生相同 artifact bytes，证明两条 row 共享同一个 blob path；删除 validation artifact 时不删除共享 blob，随后删除 run artifact，并证明最后一个引用会通过 trash staging 删除 blob。
- 更新 runner/adapters audit row 和 progress pipeline，使 artifact capture and blob lifecycle default local/storage paths 不再是 active proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Runner/Adapter Focus Refresh

已实现：

- 在 artifact/log lifecycle closure 后更新短 dashboard 和 active pipeline focus。
- Active runner/adapter queue 现在指向 remaining shared-runner edge mapping、adapter failure cleanup、Harbor unsupported-field mapping 和 SkyDiscover catalog/source precedence gaps，不再指向已经关闭的 artifact/log lifecycle family。
- 将 artifact/log capture 与 reference-counted deletion 加入 do-not-reopen summaries。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Log File Lifecycle Closure

已实现：

- 新增 `tests/test_smoke.py::test_shared_log_file_reference_counting`。
- 该测试复制一条 stored log row，使两条 log records 指向同一个 file path；删除第一条 log 时不删除共享文件，随后删除第二条 log，并证明最后一个引用会通过 trash staging 删除文件。
- 更新 runner/adapters audit row 和 progress pipeline，使 logs and hidden logs default local/adapter paths 不再是 active proof gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_shared_log_file_reference_counting -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting tests/test_smoke.py::test_shared_log_file_reference_counting tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash tests/test_smoke.py::test_non_passed_runs_still_capture_available_artifacts tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation tests/test_smoke.py::test_global_preview_bytes_controls_validation_and_run_log_previews tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Harbor Unsupported Field Matrix Closure

已实现：

- 将 `tests/test_runner_harbor.py::test_harbor_task_rejects_unsupported_fields` 扩展为 parameterized matrix。
- 该矩阵现在映射 Harbor spec 的 strict unsupported categories：multi-step tasks、non-Linux OS/platform、GPU 与 `gpu_types`、`storage_mb`、MCP servers、healthchecks、custom scheduling、external services、Docker Compose 或 multi-container runtime、host environment placeholders、raw Docker args，以及 task-declared host mounts。
- 更新 `docs/completion_audit.md`、`docs/progress.md` 和 `docs/progress_pipeline.md`，使 Harbor unsupported-field mapping 从 active work 变为已关闭的 default/fake proof gap。Real Docker-backed Harbor validation 仍保持 release-gated。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py::test_harbor_task_rejects_unsupported_fields -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_harbor.py tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_harbor.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_harbor.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_harbor.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Catalog And Source Precedence Closure

已实现：

- 扩展 `tests/test_smoke.py::test_skydiscover_catalog_ref_validation`，证明 catalog refs 使用 pinned local checkout：只存在于更新 upstream commit 的路径，在显式 catalog update 前 resolve 会失败。
- 同一个测试现在证明 dirty local catalog update rejection、拒绝时不产生 update audit，以及 cleanup 后可成功 update。
- 新增 `tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections`，覆盖 `--source-ref` rejection、explicit source conflict rejection、matching explicit-source acceptance、derived-source metadata retention，以及不会导入 whole-benchmark/private-file source。
- 新增 `tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program`，覆盖没有 initial program 时 explicit `--source-git` 和 `--source-empty` success。
- 更新 audit 和 pipeline，使 SkyDiscover source precedence 不再是 active work。剩余 SkyDiscover catalog gaps 现在收窄为 removal blockers、unexpected remote rejection 和 post-removal history observability。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_harbor.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_harbor.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_runner_harbor.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Catalog Removal And History Closure

已实现：

- 新增 `tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history`。
- 该测试证明 `catalog skydiscover remove` 会阻止仍引用 `skydiscover:` refs 的 active project configs 和 open experiments；拒绝时不会产生 remove audit，也不会删除 catalog path。
- 该测试还证明 update 会在 fetch/update 前拒绝 unexpected local catalog remote，且不会产生 update audit。
- 在 dependent project 和 experiment 都归档后，同一测试会移除 catalog，验证 removed catalog metadata 与 local path deletion，然后在 catalog checkout 不存在的情况下展示 existing experiment、run 和 log history。
- 更新 audit 和 pipeline，使 SkyDiscover catalog/ref default local-Git paths 已关闭；只剩 live upstream/network validation 属于 environment-gated。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_catalog_lifecycle tests/test_smoke.py::test_skydiscover_catalog_ref_validation tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 SkyDiscover Docker Artifact Feedback Closure

已实现：

- 扩展 `tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs`。
- Fake Docker evaluator 现在会返回 JSON `artifacts` feedback，并向 mounted workspace 写入 `captured.txt`。
- 该测试证明 JSON `artifacts` 保留在 `record_json.adapter_feedback.feedback` 中，只有 configured `workspace:captured.txt` glob 会为 baseline validation 和 experiment run records 创建 artifact rows。
- 更新 audit 和 pipeline，使 SkyDiscover Docker artifact-feedback mapping 不再是 active work；real Docker execution 仍保持 environment-gated。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_skydiscover.py::test_skydiscover_docker_runner_builds_hidden_bundle_and_parses_metrics tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py tests/test_runner_skydiscover.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py tests/test_runner_skydiscover.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py tests/test_runner_skydiscover.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` returned no matches.

## 2026-05-21 Shared Runner And Adapter Failure Cleanup Closure

已实现：

- 新增 `tests/test_runner_docker.py::test_docker_runner_timeout_removes_named_container_and_redacts_output`，覆盖 Docker timeout 的 container cleanup 和 secret redaction。
- 新增 Harbor adapter failure 覆盖：resolver-unavailable、incomplete-resolver、wrong-target-kind 和 missing-working-directory branches 都不能创建 runtime dirs；同时覆盖 verifier named container 的 timeout cleanup。
- 新增 SkyDiscover adapter failure 覆盖：Python/Docker resolver-unavailable、incomplete-resolver、wrong-target-kind 和 missing-program-path branches 都不能创建 runtime dirs；同时覆盖 SkyDiscover Docker evaluator named container 的 timeout cleanup。
- 扩展 `tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs`，在 valid project/run 后模拟本地 catalog checkout 被删除，证明 validation 与 run failures 会保存为结果、operation temp dirs 会删除，并且 visible experiment worktree 保持 clean。
- 更新 dashboard、pipeline 和 audit，使 shared-runner edge mapping 与 adapter failure cleanup 对当前 default/fake paths 关闭；剩余 runner validation 保持 real-environment gated。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py::test_docker_runner_timeout_removes_named_container_and_redacts_output tests/test_runner_harbor.py::test_harbor_adapter_resolver_failures_do_not_create_runtime_dirs tests/test_runner_harbor.py::test_harbor_timeout_removes_named_container_and_keeps_output_hidden tests/test_runner_skydiscover.py::test_skydiscover_adapter_resolver_failures_do_not_create_runtime_dirs tests/test_runner_skydiscover.py::test_skydiscover_docker_timeout_removes_named_container_and_keeps_output_hidden tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py::test_skydiscover_python_baseline_records_metrics_and_hidden_logs tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_runner_docker.py tests/test_runner_harbor.py tests/test_runner_skydiscover.py tests/test_smoke.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Project Config Schema Proof Mapping Closure

已实现：

- 新增 `tests/test_runner_local.py::test_project_config_schema_maps_runner_reward_and_env_edges`。
- 该测试映射剩余 runner/reward/artifact/env schema edges：schema version、runner type/env mode、timeout bounds、normalized runtime path escapes（包括 Windows 与 NUL shapes）、Docker host-network rejection、raw Docker passthrough rejection、Docker image/Dockerfile/context mutual requirements、platform selector aliasing 与 invalid selector rejection、build/env string-map strictness、adapter ref requirements、reward-type required fields、artifact/log limit shapes、public-source limit shapes，以及 explicit-visibility requirements。
- 收紧 `ProjectConfig`：`runner.platform` 会在 schema validation 阶段拒绝 `windows/amd64` 等非 V1 selectors，同时保留 `Linux/X64 -> linux/amd64` 这样的 Linux alias canonicalization。
- 更新 audit、dashboard 和 pipeline，使 project config/schema proof mapping 对当前 schema/default source-dependent paths 关闭。当前 active P0 queue 转向 canonical object relationship invariants。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py::test_project_config_schema_maps_runner_reward_and_env_edges tests/test_runner_docker.py::test_docker_platform_aliases_are_canonicalized_for_cache_and_cli tests/test_runner_docker.py::test_project_init_rejects_unsupported_docker_platform_architecture -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_runner_local.py tests/test_runner_docker.py::test_docker_platform_aliases_are_canonicalized_for_cache_and_cli tests/test_runner_docker.py::test_project_init_rejects_unsupported_docker_platform_architecture tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/configs.py tests/test_runner_local.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/configs.py tests/test_runner_local.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/configs.py tests/test_runner_local.py docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Progress Guardrail Split

已实现：

- 将 duplicate-work guardrails 从 `docs/progress_pipeline.md` 拆到 `docs/progress_closed_gaps.md`。
- 新增同步的 `docs/progress_closed_gaps_cn.md`。
- 缩短 `docs/progress_pipeline.md`，现在只承载 active batch、active queue、guardrail pointer、full-suite policy 和 update checklist。
- 更新 `docs/progress.md`、`README.md`、`AGENTS.md`、`docs/completion_audit.md` 与本 log，指向新的 dashboard/pipeline/guardrail/log/audit 阅读路径。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" README.md README_cn.md AGENTS.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md docs/completion_audit.md docs/completion_audit_cn.md` 无匹配。

## 2026-05-21 Project And Experiment Retained-Row Invariant Closure

已实现：

- 扩展 `tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths`。
- 扩展 `tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash`。
- 这些测试现在断言 experiment/project hard remove 会删除 primary rows，同时将 `path_registry` rows 保留为 `removed`、将 credentials 保留为 `revoked`、保留非空 removal/revocation timestamps，并让 `path_registry.removed_by_credential_id` 与 remove audit actor credential 对齐。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使这个 retained-row invariant family 不再是模糊 active work。剩余 canonical object relationship work 仍在其他 object families 和 visibility joins 上保持 active。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash -q`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Public From-Experiment Visibility Intersection Closure

已实现：

- 扩展 `tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound`。
- 该测试现在覆盖 public `exp create --from-exp` 在 current project visibility `none`、current explicit project visibility 中 source experiment 被列入和未列入，以及 source experiment 的 stored explicit upper bound 省略自身时的行为。
- 允许通过的 explicit case 断言 stored `creation_origin.kind = from_exp`；被阻止的 explicit cases 断言 stable `SCOPE_VIOLATION`、无 experiment row、无 worktree creation。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 public inheritance visibility intersection 不再是宽泛 active work。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Source And Validation Hard-Remove Relationship Closure

已实现：

- 扩展 `tests/test_smoke.py::test_config_source_observe_and_tags`。
- 该测试现在证明 source remove 会通过阻止删除任何被 stored project config version 引用的 source 来保留 immutable config-version reproducibility，同时保留 source row 和 Git ref。
- 同一路径证明可移除 source hard remove 会删除 source row 和 Git source ref，保存 source-ref deletion metadata，并把 archived dependent experiments 保留为 denormalized history。
- Validation remove 现在断言 remove audit row 带有 admin actor credential、generic action/object ids、cascade flag，以及 child artifact/log deletion metadata。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使这个 source/validation relationship family 不再是宽泛 active object-model work。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Maintenance Object Audit Metadata Closure

已实现：

- 扩展 `tests/test_smoke.py::test_auth_init_and_config_show`，断言 backup prune、zero-count cache prune 和 stale lock clear audit actor/action/object/cascade/metadata rows。
- 扩展 `tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries` 和 `test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry`，断言 trash/Docker-warning cache prune audit metadata，包括 actor、prune counts 和 warning counts。
- 扩展 `tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history`，断言 catalog remove audit actor/action/object/cascade/reason/schema metadata。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 backup/cache/lock/catalog maintenance audit metadata 不再是 active object-model work。当时剩余 active evidence 转向 visibility joins 和 grouped audit-row decomposition。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Explicit Token And Inspection Visibility Closure

已实现：

- 扩展 `tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility`。
- 该测试现在导入 explicit project visibility policies，并证明 worktree token 会保留 own-experiment visibility，同时能读取 explicit-listed peer experiments、runs、artifacts 和 logs。
- 同一测试证明 inspection token 使用相同的 explicit visibility intersection，能读取 explicit-listed peer experiment/run records，并且对存在但未列入的 experiments 仍返回 non-disclosing `SCOPE_VIOLATION`。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 explicit token/inspection observe visibility joins 不再是 active work。剩余 active evidence 是 observe filter/sort row mapping 和 grouped audit-row decomposition。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Experiment Observe Matrix Queue Refresh

已实现：

- 关闭当前 default local visible/admin paths 下剩余的 experiment list/search/best filter、pagination 和 sort matrix。
- 更新 `docs/progress.md` 和 `docs/progress_pipeline.md`，使 active P0 现在是 grouped audit-row decomposition，而不是 observe filter/sort work。
- 详细 closure 记录已写在本日志较早的 `2026-05-21 Experiment Observe Filter And Sort Matrix Closure` 小节。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Credential Audit Metadata Closure

已实现：

- 扩展 `tests/test_smoke.py::test_auth_init_and_config_show`，断言 root credential regenerate audit actor/action/object/cascade metadata、revoked credential references，以及 raw root key material absence。
- 扩展 `tests/test_smoke.py::test_config_source_observe_and_tags`，断言 admin key create/revoke audit actor/action/object/cascade metadata、revoke metadata，以及 raw root/admin key material absence。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 credential audit metadata 不再是最弱的 grouped audit-row evidence target。剩余 active evidence 是下一个 grouped audit-row decomposition 加 release gates。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_auth_init_and_config_show tests/test_smoke.py::test_config_source_observe_and_tags tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Inspection Context Repair Pinned Commit Closure

已实现：

- 扩展 `tests/test_smoke.py::test_context_self_repair_requires_registered_branch`。
- 该测试现在创建 moved inspection checkout，证明 self-token repair 会拒绝 mismatched pinned inspection commit，且不改变 active registry row、不写 repair audit；回到 pinned commit 后允许 self-token repair。
- 成功 repair 路径现在断言 active inspection `path_registry` row 已更新，并且 `inspection_checkout` repair audit 带有 token actor/action/object/cascade fields 和 schema-versioned context repair metadata。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 inspection context repair pinned-commit/audit metadata 不再是 active grouped context-repair gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Token Credential Side-Effect Evidence Mapping

已实现：

- 将现有 token regenerate/revoke evidence 映射进 credential 和 audit rows，避免继续作为重复的宽泛 gap。
- `tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec` 证明 token regenerate/revoke audit metadata、registered path hashes，以及 result/audit output 中不渲染 raw token。
- `tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights` 证明 regeneration 后 old-token revocation、new-token activation、marker token-id update、raw token rotation，以及 private annotation continuity。
- 更新 dashboard、pipeline 和 closed-gap guardrails，使 token revoke/regenerate side-effect mapping 不再作为 unresolved credential evidence 排队。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Context Marker Conflict And Alias Closure

已实现：

- 新增 `tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free`。
- 该测试证明 symlink aliases 会解析到 registered project context，exact missing markers 返回 `CONTEXT_NOT_FOUND`，invalid marker JSON 返回 `CONTEXT_CONFLICT`，错误 marker home ids 在 `context show` 和 `context repair` 都会失败，并且 marker/registry disagreement 会在 context detection 阶段失败。
- 每个 failure branch 都断言 `path_registry` snapshot 和 repair audit count 保持不变。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 marker/registry disagreement、missing marker、symlink alias 和当前 marker/home mismatch variants 不再是 active grouped context gaps。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free -q`

## 2026-05-21 Credential Model Proof Closure

已实现：

- 硬化 low-level credential verification，使 required-scope、project、token-mode、token-path、type-prefix/type-row、revoked-row、unknown-id、malformed 和 verifier mismatch failures 都返回 generic `AUTH_DENIED: invalid credential`。
- 新增 `tests/test_auth.py::test_credential_verification_failures_do_not_reveal_failure_part`，覆盖 non-disclosing auth-denial variants。
- 新增 `tests/test_auth.py::test_credential_generation_uses_high_entropy_secret_and_salt_sources`，证明 raw credential secrets 使用 `secrets.token_hex(32)`，每个 credential 的 salt 使用 `secrets.token_bytes(32)`。
- 新增 `tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free`，证明 project admin keys 只能 list same-project credentials，不能使用 root credential listing，不能 create/revoke credentials，且 rejected authority paths 不改变 database。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 malformed credential variants、project-admin authority edges 和 raw secret entropy/source generation 不再是 active credential-model gaps。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_key_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_auth_root_regenerate_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_key_command_success_fields_follow_cli_spec -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_auth.py tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free tests/test_cli_contract.py::test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects tests/test_cli_contract.py::test_key_command_success_fields_follow_cli_spec tests/test_cli_contract.py::test_auth_root_regenerate_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/auth.py tests/test_auth.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/auth.py tests/test_auth.py tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/auth.py tests/test_auth.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 V1 Security Boundary Negative Proof Closure

已实现：

- 新增 `tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts`。
- 该测试证明 V1 没有 encryption/grant/rewrap dependency roots 或 runtime import roots，也没有 encrypted storage、grant files、public grants、token rewrap、DEKs、ciphertext、keyring 或 cryptography 的 implementation/schema artifacts。
- 该测试还固定 README 和 blueprint wording：ALab V1 是 plaintext local storage 和 collaboration boundary，不是 strong local multi-user security product。
- 更新 audit、dashboard、pipeline 和 closed-gap guardrails，使 encrypted-storage/grant/rewrap absence 以及 public/status/hidden security-boundary mapping 不再是 active V1-boundary gaps。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies tests/test_cli_contract.py::test_public_status_excludes_private_project_history_and_runtime_fields tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Closeout Gate And Capability-Refresh Mapping

已实现：

- 在 completion audit 中把 `config validate --refresh-capabilities` 映射到 fake/default Docker capability cache tests、native-platform fallback test，以及 platform/resource pre-write rejection tests。
- 将 active pipeline 切换为 closeout mode，使未来工作只从 named audit defects 或明确 release-target environment gates 开始。
- Real Docker、Harbor、live SkyDiscover 和 network/native dependency checks 继续作为明确的 `ENV-GATED` release validation，不把它们当成 default-suite proof。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`

## 2026-05-21 Public Git Credential-Helper Warning Proof

已实现：

- 扩展 `tests/test_smoke.py::test_public_exp_create_inline_source_import`，加入隔离的 no-helper Git config path，覆盖 public `--source-git`。
- 该测试现在证明：当 `GIT_CONFIG_GLOBAL` 没有 helper 且 `GIT_CONFIG_NOSYSTEM=1` 时，public Git inline source import 不渲染 `PUBLIC_GIT_CREDENTIAL_HELPER_USED` warning；原有隔离 helper path 仍会渲染该 warning，并将其持久化到 source-origin metadata。
- 更新 completion audit、dashboard、pipeline 和 closed-gap guardrails，使 public `--source-git` helper-available/helper-unavailable warning behavior 不再是 active public inline source gap。
- 因为本 batch 在 closeout full-suite pass 后改动了 tests 和 documentation，已将 full default-suite gate 标为 stale。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Context Repair Old-Path Blocker Proof

已实现：

- 扩展 `tests/test_smoke.py::test_context_self_repair_requires_registered_branch`，加入一个复制出来的 duplicate worktree；该 worktree 带有效 marker/token，但原 registered worktree path 仍存在。
- 该测试现在证明 self-token `context repair` 会以 `CONTEXT_CONFLICT: registered path still exists` 失败，并保持 active `path_registry` row 和 repair audit count 不变。
- 更新 completion audit、dashboard、pipeline 和 closed-gap guardrails，使 old registered-path-still-exists blockers 不再是 active context repair gap。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_context_self_repair_requires_registered_branch tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free tests/test_cli_contract.py::test_project_context_repair_accepts_ambient_admin_key -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_smoke.py`
- `git diff --check`

## 2026-05-21 Project Config Edit Semantics Proof Mapping

已实现：

- 将 runtime baseline trigger and config edit semantics audit row 重新归类为当前 config mutation surfaces 已证明。
- 把 `tests/test_smoke.py::test_project_config_validation_edges` 精确映射到 spec rules：latest-attempted edits、runtime baseline triggers、byte-identical no-op edits、metadata-only inherited edits、monotonic revert versions，以及 `project config set/import --dry-run` no-write behavior。
- 通过既有 smoke 和 CLI-contract tests 继续关联 invalid runtime preservation 与 output/preflight evidence。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_invalid_runtime_config_preserves_previous_active_valid_config tests/test_cli_contract.py::test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads tests/test_cli_contract.py::test_project_config_mutation_and_validate_success_fields_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Project Init Precedence Proof Mapping

已实现：

- 将 project-init input precedence audit row 重新归类为当前 local/Git/empty/Harbor/SkyDiscover init paths 已证明。
- 映射了 mode-specific source-origin requirements、duplicate init option rejection、source-ref injection/mismatch cleanup、source-limit failures before rows/staged paths、malformed/negative source limit pre-write failures、retained invalid project baseline failures、one-time raw admin key rendering，以及 adapter-derived editable-source precedence/conflict/fallback paths 的直接证据。
- 因为这是 closeout pass 之后的 documentation/test batch，full default-suite gate 继续保持 stale。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin tests/test_smoke.py::test_project_init_source_ref_mismatch_cleans_staged_paths tests/test_smoke.py::test_project_config_validation_edges tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error tests/test_smoke.py::test_harbor_project_init_uses_declared_source_and_excludes_private_assets tests/test_smoke.py::test_adapter_init_rejects_conflicting_explicit_source tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program tests/test_cli_contract.py::test_registered_command_typed_value_options_reject_invalid_values_without_side_effects tests/test_cli_contract.py::test_project_init_mode_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_project_init_adapter_mode_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_one_time_raw_key_outputs_follow_cli_secret_rules tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`

## 2026-05-21 Source Import Tree-Hash And Remote-Git Fidelity Proof

已实现：

- 修正 `canonical_tree_hash`，使 manifest entries 按 repo-relative path 全局排序，并在 `os.walk` traversal 中纳入 symlinked directory entries，而不是跳过它们。
- 更新 source copying，使 plain 和 Git worktree imports 会把 symlinked directories 保留为 symlink entries，同时仍然拒绝 Git submodules/gitlinks。
- 新增 `tests/test_smoke.py::test_canonical_tree_hash_manifest_matches_v1_spec`，覆盖精确的 `alab-tree-sha256-v1` manifest entry order 以及 regular-file/executable/symlink entry 内容。
- 扩展 `tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules`，覆盖 standalone remote `source import --source-git --source-subdir`，包括 filtered subdir contents、stored canonical tree hash、resolved commit metadata、sanitized origin metadata without raw source URL/path，以及 admin import 不产生 warning。
- 将 source model/source import audit row 重新归类为当前 local/Git/empty source import/model paths 已证明，并加入 closed guardrail。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_canonical_tree_hash_manifest_matches_v1_spec tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived tests/test_smoke.py::test_source_import_empty_after_filter_warns tests/test_cli_contract.py::test_source_import_origin_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_source_import_warning_success_fields_follow_cli_spec tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/source_import.py tests/test_smoke.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/source_import.py tests/test_smoke.py`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/source_import.py tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Experiment Create Source-Binding Proof Mapping

已实现：

- 将 experiment-create source-binding/default-source audit row 重新归类为当前 exp-create source-binding paths 已证明；更宽的 visibility 仍由 dedicated visibility row 跟踪。
- 映射 default-source creation、inline local/Git/empty/subdir imports、source dedupe、public source-import policy ceilings 和 disabled-public behavior、admin archived-source `--source-ref` binding、`--from-exp` latest/final/best/SHA resolution、closed/archived source-experiment behavior、mutable override narrowing、token creation with raw-token non-rendering，以及 selector/conflict no-write failures 的直接证据。
- 新增 closed guardrail，避免后续 batch 在没有新增 selector、metadata field、token mode、mutable field 或 visibility scope 时重复打开 `exp create` source-binding work。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_exp_create_inline_source_import tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_admin_exp_create_can_bind_archived_source_ref tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_cli_contract.py::test_experiment_create_inline_source_variants_success_fields_follow_cli_spec tests/test_cli_contract.py::test_experiment_create_from_exp_success_fields_follow_cli_spec tests/test_cli_contract.py::test_experiment_create_source_ref_success_fields_follow_cli_spec tests/test_cli_contract.py::test_non_remove_documented_conflicts_fail_without_side_effects tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Run And Submit Lifecycle Proof Mapping

已实现：

- 将 run/submit lifecycle audit row 重新归类为当前 local/default run-submit paths 已证明，同时让 adapter-specific runner result failures 继续归在 runner rows。
- 映射 parser preflight、byte limits、project/experiment/worktree state blockers、operation locks、stale running-record interruption、invalid Git states、running-record-before-auto-commit ordering、mutable-scope rollback and metadata、contextless runner workspaces、final-run success and failure behavior、summary/feedback/ref input rules、secret-value rejection、non-disclosing invisible/missing ref failures，以及 failed/timeout/error runs 不写 final-submission rows 的直接证据。
- 新增 closed guardrail，避免未来在 run/submit 没有新增 Git-state checks、mutable-scope semantics、ref visibility rules、payload modes、result statuses 或 operation-lock behavior 时重复打开 run/submit lifecycle work。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_local_project_run_submit_workflow tests/test_smoke.py::test_submit_result_failures_and_input_preflight tests/test_smoke.py::test_run_enforces_experiment_mutable_scope tests/test_smoke.py::test_run_writes_running_record_before_auto_commit_without_long_write_tx tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock tests/test_smoke.py::test_run_rejects_invalid_git_states tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed tests/test_smoke.py::test_stale_running_records_are_interrupted tests/test_cli_contract.py::test_run_result_failures_follow_cli_spec tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit tests/test_cli_contract.py::test_submit_result_failures_follow_cli_spec tests/test_cli_contract.py::test_submit_success_fields_follow_cli_spec tests/test_cli_contract.py::test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Aggregate Project/Observe Visibility Proof Mapping

已实现：

- 在 detailed rows 已有直接证据的前提下，将 aggregate project/source/config/experiment/observe evidence rows 重新归类为当前 default/local paths 已证明。
- 将 visibility model row 重新归类为当前 public、token、inspection、observe read 和 annotation authorization surfaces 已证明。
- 继续把 release gates 与 top-level completion gates 分开：当前 worktree 的 full default-suite verification 仍然 stale，真实 Docker/network/service gates 仍然是 `ENV-GATED`。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations tests/test_cli_contract.py::test_project_context_help_capability_display_uses_context_and_explicit_credentials tests/test_cli_contract.py::test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials tests/test_cli_contract.py::test_inspection_context_help_capability_display_uses_inspection_token_and_explicit_credentials tests/test_cli_contract.py::test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Current Worktree Full Default-Suite Gate

已实现：

- 在 source-import/tree-hash code/test changes 和 documentation proof-mapping batches 后，重新运行 default closeout gate。
- 将 full default-suite gate 重新归类为当前 worktree 已证明。
- Real Docker/network/service gates 继续保留为明确的 `ENV-GATED` release validation。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/source_import.py tests/test_smoke.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。
- 记录后 docs sanity：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`

## 2026-05-21 Documentation Consistency Closeout

已实现：

- 为当前 documentation set 运行 final documentation consistency pass。
- 将 documentation consistency P0 gate 和 documentation/milestone blueprint row 重新归类为当前 README/spec/progress/audit/local-note state 已证明。
- 将 local-only product-scope row 重新归类为当前 surface 已证明，因为 runtime-surface guard 和 manual documentation pass 已覆盖先前打开的 docs/README consistency condition。
- 更新 ignored local `AGENTS_cn.md` note，使其与 `AGENTS.md` 中 dashboard、pipeline、closed gaps、historical log 和 completion audit 的拆分保持一致。
- 从 active queue 移除 final docs consistency pass，并新增 closed guardrail。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_readme_repository_structure_trees_are_synchronized_and_existing tests/test_cli_contract.py::test_local_agent_notes_and_env_files_are_gitignored tests/test_cli_contract.py::test_env_example_documents_setup_environment_variables tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies tests/test_cli_contract.py::test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts tests/test_cli_contract.py::test_cli_primary_object_type_tables_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_surface_coverage_is_synchronized tests/test_cli_contract.py::test_english_and_chinese_command_option_contracts_are_synchronized tests/test_cli_contract.py::test_english_and_chinese_conflict_option_contracts_are_synchronized tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_registered_command_success_field_contracts_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md AGENTS_cn.md` 无匹配。

## 2026-05-21 Runtime Stack And Typer Boundary Proof

已实现：

- 在 `src/alab/cli.py` 中为真实 console entrypoint 增加 Typer app boundary，同时保留既有 `cli.run(argv)` service-facing parser 和 command semantics。
- 禁用 Typer 自身 help interception，并配置为透传 arbitrary argv，使 ALab 的 global pre-scan、context-aware help 和 command preflight 仍是权威逻辑。
- 新增 `tests/test_cli_contract.py::test_runtime_stack_and_entrypoint_follow_blueprint_contract`，证明 pyproject stack contract、console-script entrypoint、uv package mode、Python/Ruff targets、runtime dependency roots、Typer/`sqlite3`/Pydantic imports、dynamic `tomli-w`/`pathspec` usage、Typer app delegation，以及稳定的 console help/error behavior。
- 将 runtime stack and architecture audit row 重新归类为当前 local/runtime stack 已证明，并加入 closed guardrail。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_runtime_stack_and_entrypoint_follow_blueprint_contract tests/test_cli_contract.py::test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies tests/test_cli_contract.py::test_output_rich_is_single_command_and_non_persistent -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check src/alab/cli.py tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src/alab/cli.py tests/test_cli_contract.py`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run alab --help`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run alab not-a-command`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" src/alab/cli.py tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-21 Lifecycle Evidence Map Closeout

已实现：

- 新增 `tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces`。
- 将每个当前 registered archive/unarchive command，以及每个当前 registered lifecycle hard-remove/cleanup remove command 映射到直接 runtime evidence；immediate tag removal 没有 archive state，因此例外。
- 将 lifecycle direction 与 lifecycle remove/idempotency audit rows 重新归类为当前 registered default/local lifecycle surfaces 已证明。
- 新增 closed guardrail，让未来 batch 更新 evidence map，而不是重新从头阅读宽泛 lifecycle smoke tests。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- Focused docs sanity：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- Full default suite：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- Full static checks：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`；`PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`；`git diff --check`

## 2026-05-21 Home Filesystem And Path Registry Evidence Map

已实现：

- 新增 `tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current`。
- 将 home resolution/layout、path-registry hashing/reuse、context marker contracts/conflicts，以及 worktree/checkout/repair path evidence 映射到精确 tests。
- 将 ALab home/filesystem layout、home resolution 和 context marker/path-registry audit rows 重新归类为当前 default/local behavior 已证明。
- 将 full default-suite gate 标为 stale，因为本 batch 在上次 full-suite pass 后修改了 tests 和 docs。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`

## 2026-05-21 Final Default-Suite Closeout Gate

已验证：

- 在 home/filesystem/path-registry evidence-map 和 host-support policy proof batch 后，重新运行完整 default/local gate。
- 将 P0 full default-suite gate 重新归类为当前 worktree 已证明。
- 从 active queue 移除 full-suite rerun 项；未来只有 implementation/test changes 后，或 release claim 前，才重新加入。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md tests/test_cli_contract.py` 无匹配。

## 2026-05-22 Source And Runner Direction Evidence Maps

已实现：

- 新增 `tests/test_cli_contract.py::test_source_public_experiment_evidence_map_refs_stay_current`。
- 新增 `tests/test_cli_contract.py::test_runner_adapter_evidence_map_refs_stay_current`。
- 将 source/public experiment direction row 重新归类为当前 default/local paths 已证明。
- 将 runner/adapter direction row 重新归类为 default/fake paths 已证明，同时真实 Docker/network/native dependency gates 继续保持 `ENV-GATED`。
- 更新 dashboard、pipeline 和 closed-gap guardrails，防止未来在没有 named edge 时重开这些宽泛 family。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_source_public_experiment_evidence_map_refs_stay_current tests/test_cli_contract.py::test_runner_adapter_evidence_map_refs_stay_current tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Core Successful Workflow Closeout

已实现：

- 将 top-level core successful workflow row 重新归类为当前 default/local/fake-adapter workflow 已证明。
- 将该 closeout 绑定到已证明的 public/private collaboration rows、adapter-derived source rows、lifecycle rows、runner/adapter rows，以及 2026-05-22 full default-suite rerun。
- 更新 dashboard、pipeline 和 closed-gap guardrails，防止未来 agent 在没有 named audit edge 时重开宽泛 core workflow proof。

验证：

- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Observe Collaboration Audit Wording Refresh

已实现：

- 替换 observe/collaboration intro 中仍写多数行是 `PARTIAL` 的过期说明；当前 default/local surfaces 的表内各行已是 proved。

验证：

- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Storage Audit Object Evidence Map

已实现：

- 新增 `tests/test_cli_contract.py::test_storage_audit_object_evidence_map_refs_stay_current`。
- 将 schema/index/JSON contracts、maintenance/catalog audit metadata、credential/token/context audit metadata、lifecycle retained-row/trash relationships，以及 annotation/visibility audit relationships 映射到精确 tests。
- 将 core object model、SQLite retained-row relationship 和 audit event retention rows 重新归类为当前 default/local object families 已证明。
- 更新 dashboard、pipeline 和 closed-gap guardrails，防止后续在没有 named edge 时重开这个 storage/audit/object proof family。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_storage_audit_object_evidence_map_refs_stay_current -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_storage_audit_object_evidence_map_refs_stay_current tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Capability Help And Payload Preflight Closeout

已实现：

- 将 context-aware help/capability preflight rows 重新归类为当前 generated/default/context surfaces 已证明。
- 将 file/output payload preflight row 重新归类为当前 text payload readers、stdin/file conflicts、output parent checks 和 `OUTPUT_EXISTS` behavior 已证明。
- 更新 dashboard、pipeline 和 closed-gap guardrails，确保除非新增 registered command、context mode、credential surface 或 payload option 改变矩阵，否则不重开这些 preflight families。

验证：

- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Real Docker-Backed Gate Closeout

已实现：

- 修正 opt-in real Docker CLI workflow test，使其期望当前 `project init` 对隐藏 Docker setup output 渲染的 warning field。
- 将 real Docker-backed subset 重新归类为当前 Darwin/Docker Desktop host 已证明：Docker runner、Dockerfile cache、CLI Docker workflow、Harbor verifier variants 和 SkyDiscover Docker evaluator。
- Live SkyDiscover catalog 与 SkyDiscover Python local-wheel/network/native dependency gates 继续明确保持 `ENV-GATED`。
- 更新 dashboard、pipeline、audit 和 closed-gap guardrails，避免未来在 host/platform 未变化时重复打开 real Docker-backed subset。

验证：

- `ALAB_RUN_REAL_DOCKER=1 UV_LOCKED=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest tests/test_real_docker.py::test_real_docker_cli_project_run_workflow -q`
- `ALAB_RUN_REAL_DOCKER=1 UV_LOCKED=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run pytest -m real_docker -q`
- 本次 closeout batch 的 full default-suite/static checks 记录在 P0 completion gate 中。

## 2026-05-22 SkyDiscover Python Dependency Gate Closeout

已实现：

- 将 SkyDiscover Python local-wheel/cache、networked dependency 和 native dependency opt-in gates 重新归类为当前 Darwin host 已证明。
- 确认 live SkyDiscover catalog gate 仍是 environment-gated，因为此环境无法通过 SSL 访问 GitHub，不是 ALab implementation failure。
- 更新 audit、dashboard、pipeline 和 guardrails，使唯一剩余 real-environment runner gate 收缩为 live SkyDiscover catalog reachability。

验证：

- `ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -m real_skydiscover_python -q`（`1 passed, 3 skipped`）
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_DEFAULT_INDEX=https://pypi.org/simple pytest -m networked_skydiscover_python -q`（`2 passed`）
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_DEFAULT_INDEX=https://pypi.org/simple pytest -m native_skydiscover_python -q`（`1 passed`）
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 pytest -m live_skydiscover_catalog -q -rs` 因 GitHub 返回 `LibreSSL SSL_connect: SSL_ERROR_SYSCALL` 被 skip。
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Real Docker Capability Refresh Gate Closeout

已实现：

- 新增 opt-in real Docker `config validate --refresh-capabilities` 测试：要求 daemon 可达，验证渲染的 capability rows，并检查持久化的 Docker availability、Linux platform、architecture、CPU 和 memory resource rows。
- 将 global config 的 real Docker refresh row 重新归类为当前 Darwin/Docker Desktop host 已证明；不同 release-target Docker daemons 仍保持 opt-in。
- 更新 audit、dashboard、pipeline 和 guardrails，避免未来在 host/platform/Docker version 未变化时重新打开当前 real Docker capability refresh。

验证：

- `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_real_docker.py::test_real_docker_config_validate_refreshes_capability_cache -q`
- `ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -m real_docker -q`（`10 passed`）
- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q src tests`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_real_docker.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 CLI Audit Summary Closeout

已实现：

- 新增 `tests/test_cli_contract.py::test_completion_audit_cli_evidence_rows_are_not_stale`，使 P0 CLI gate、product CLI/output row、CLI summary row 和拆分后的 CLI long-tail rows 不能互相矛盾。
- 将 CLI golden/command-contract completeness 重新归类为当前 registered CLI surfaces 已证明，因为拆分后的 CLI long-tail rows 现在覆盖 parser、renderer、capability、success-schema、saved result-failure、system-error、error/warning catalog、payload 和 documentation-contract evidence。
- 更新 dashboard、pipeline 和 guardrails，避免未来在没有 named command/output change 时重新打开 CLI golden/command-contract completion。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_completion_audit_cli_evidence_rows_are_not_stale tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest -q`
- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked ruff check tests/test_cli_contract.py`
- `PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache python3 -m compileall -q tests/test_cli_contract.py`
- `git diff --check`
- `rg -n "[ \t]+$" tests/test_cli_contract.py docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Live SkyDiscover Catalog Gate Closeout

已实现：

- 在当前网络环境重新运行 opt-in live SkyDiscover catalog marker；本次通过而不是 skip。
- 将当前 live SkyDiscover catalog 和 real-environment runner rows 重新归类为当前 Darwin host 已证明，并与此前已证明的 real Docker-backed 与 SkyDiscover Python dependency gates 对齐。
- 更新 dashboard、pipeline、completion audit 和 closed-gap guardrails，使 active queue 现在只保留 grouped blueprint/subsystem audit-row decomposition。Release-target host、platform、Docker、Python dependency 或 upstream SkyDiscover catalog 发生变化时，仍必须重跑对应 opt-in gates。

验证：

- `UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked env ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 pytest -m live_skydiscover_catalog -q -rs`（`1 passed`）
- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。

## 2026-05-22 Final Requirement Ledger Closeout

已实现：

- 确认除 status legend 和 future-state instructions 外，没有 active `PARTIAL`、`PENDING` 或 `ENV-GATED` requirement rows 后，将 top-level blueprint/subsystem requirement audit gate 重新归类为当前 V1 evidence ledger 已证明。
- 清空当前 worktree 的 active pipeline queue，并更新 dashboard/closed-gap guardrails，使未来工作按新的 scoped changes 处理，而不是继承旧 backlog。
- Release-target real-environment reruns 继续只在 host/platform/Python/network/upstream behavior 变化时触发。

验证：

- ``rg -n '^\| .* \| `PARTIAL`|^\| .* \| `PENDING`|^\| .* \| `ENV-GATED`' docs/completion_audit.md docs/completion_audit_cn.md`` 无 active requirement-row 匹配。
- Focused docs sync：`UV_CACHE_DIR=/private/tmp/alab-uv-cache PYTHONPYCACHEPREFIX=/private/tmp/alab-pycache uv run --locked pytest tests/test_cli_contract.py::test_root_and_docs_markdown_files_have_synchronized_chinese_pairs tests/test_cli_contract.py::test_selected_english_and_chinese_success_fields_are_synchronized -q`
- `git diff --check`
- `rg -n "[ \t]+$" docs/completion_audit.md docs/completion_audit_cn.md docs/progress.md docs/progress_cn.md docs/progress_pipeline.md docs/progress_pipeline_cn.md docs/progress_closed_gaps.md docs/progress_closed_gaps_cn.md docs/progress_log.md docs/progress_log_cn.md` 无匹配。
