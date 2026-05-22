# ALab

ALab 是一个本地、agent-first 的 Python CLI 实验工作台。它面向这样的工作流：外部 agent 在 ALab 创建的 Git worktree 中工作，运行评估，提交最终结果，并通过明确的协作可见性规则查看历史 experiment。

项目现在已有可运行的本地 workflow 里程碑。V1 产品契约仍以 [docs/blueprint.md](docs/blueprint.md) 为规范性来源，`docs/` 下包含同步的子系统 specs，中文版本使用 `*_cn.md` 命名。

## Highlights

- Local-only V1：无 server、sync service、Web UI、内置 agent launcher 或 account system。
- Agent-first CLI：默认和持久化输出都是 plain text；Rich output 只能通过 `--output rich` 对单次命令启用。
- Context-aware command surface：`alab`、`alab help` 和 command preflight 会按当前 project、experiment、inspection context 以及 explicit key，只显示并允许当前可用 commands。
- 协作边界，不是本地强安全隔离：root/admin key 和 experiment token 用于 CLI 权限控制，project records 是本地明文数据。
- Secret hygiene：不存 raw key/token；`secret_env` 值是本地 plaintext，但不渲染或 export；configured secrets 会从 logs 中 redacted。Artifact export 是精确捕获的 bytes，不会自动 redacted。
- Project/experiment model：project 定义 task、source、runner、reward、artifact、mutable scope 和 visibility；experiment 是隔离 Git branch 和 worktree。
- Immutable source snapshots：local、Git、empty、Harbor task source 与 SkyDiscover initial program 都表示为 canonical project repository 中的 source ref。
- Multi-source projects：一个 project 可以保留多个 source；每个 active config 有一个 default source；每个 experiment 创建时绑定且只绑定一个 source。
- 分阶段实现：核心里程碑让 local/Git/empty source 和 local runner 可用；Docker image/Dockerfile config、Harbor verifier、SkyDiscover Python evaluator 和 SkyDiscover Docker evaluator 现在已通过同一 runner contract 执行。
- Implementation model：当前 scaffold 提供 Python CLI entry point、显式 `sqlite3` storage、Pydantic config boundary models，以及只消费 command result objects 的 renderer。V1 command registry 已建立，后续 commands 在清晰实现边界后补齐。
- Baseline validation：project init 和 runtime-affecting config change 默认运行 baseline test。
- Public bootstrap：project 默认允许本地 no-key experiment creation，可从 existing source、inline source import 或可见 open/closed experiment 创建，public from-experiment inheritance 受 source experiment visibility bound 限制，方便 agent 使用，但不授予 project-management 或 observe-history access。
- Inspection checkout：只读 CLI context 可通过 scoped token observe/export，不会变成 submit-capable experiment。
- Explicit lifecycle model：archive/unarchive 是幂等可逆状态，remove 是带 dry-run blocker 的 audited archive-first deletion，worktree/inspection 和 dependent run/validation artifact/log remove 会按 reference counting 把 filesystem path stage 到 ALab trash，prune/gc 只清理 non-authoritative data。
- Runner plan：已实现 local runner；Docker 支持 explicit image/Dockerfile execution、`default|none` network、host workspace/run mount、感知 `.dockerignore` 的 build cache key、缺失 image auto-pull、runtime capability cache refresh，以及 ALab-owned image cache pruning；Harbor verifier 与 SkyDiscover Python/Docker evaluator 现在会物化 hidden bundle，并把 raw verifier/evaluator output 存为 hidden logs。

## Current Status

第一阶段可运行实现包括：

- 带 `pyproject.toml`、`src/alab/`、tests 和 `alab` entry point 的 package scaffold。
- Strict text object rendering、稳定 error object rendering、global option pre-scan、context-aware help 和 command preflight。
- ALAB home 初始化、带 checksum validation 和升级前 backup 的 file-backed SQLite migration loading、SQLite WAL schema、root/admin/token verifier storage、project control context marker、experiment token file、在 case-insensitive filesystem 上使用大小写归一化 hash 的 path registry record，以及带 self-token Git branch/pinned-commit checks 的 `context show/repair`。
- 从 local/Git/empty source origin 初始化 local project、canonical source ref、baseline validation、local runner execution、log/artifact storage、experiment worktree creation、run、submit、status/list、observe runs/logs/artifacts，以及 audit list/show。
- Root/admin key create/list/revoke、project config show/export/import/set、project env set/unset/list、project secret set/unset/list/gc（不渲染 raw secret value）、manual project validation、validation archive/unarchive/remove、stale lock clearing、backup prune 和 cache prune。
- Init 后 source import/show/list/archive/unarchive/remove dry-run、针对 tracked/untracked files、`.gitignore`、`.alabignore`、built-in sensitive excludes 和 empty-filter warning 的 Git-aware local source filtering、experiment archive/unarchive/remove dry-run、project archive/unarchive/remove dry-run，以及 experiment tag add/remove/list。
- Experiment worktree remove/restore、experiment token list/revoke/regenerate、inspection checkout create/remove、带 trash staging 和 missing-path reconciliation 的 worktree/inspection filesystem removal、面向 branch ref/worktree/inspection/log/artifact path 的 experiment remove cascade staging、带 reference-counted trash staging 的 standalone artifact/log remove、支持 dependent artifact/log row 且记录 latest/final-run metadata 的 `run remove --cascade`、带 dependent artifact/log reference-counted trash staging 的 validation remove、带 revision-count remove audit、Git-backed path/line target validation 和 observe annotations list/show 的 annotation add/edit/archive/unarchive/remove、面向 project root/control path/registered worktree/inspection checkout 的 project whole-tree remove cascade staging、保留并 revoke token/path rows、trash cache pruning、experiment/run/artifact/log/annotation list surfaces 的 documented observe filters 和 sort whitelists、受 source experiment visibility 限制的 public `--from-exp` experiment creation、带 project policy limits 与 public `--source-git` credential-helper warning 的 public `exp create --source-*` inline source import，以及带 same-project/explicit token visibility 和 best incomparable-run warning 的 experiment observe list/search/show/best。
- Docker runner 已支持 explicit `runner.image` 和 `runner.dockerfile` config execution，包括 container-visible ALab env、`default|none` network selection、Dockerfile cache key computation、runtime capability cache refresh、针对 `linux/amd64` 和 `linux/arm64` 的 per-architecture platform capability checks、对 unsupported configured platform/resource limit 的 pre-write rejection、ALab-owned image tag pruning，以及不需要 daemon 的 fake-Docker contract tests。
- SkyDiscover catalog add/update/show/remove 已支持 exact commit pinning、本地 Git cleanliness checks、configured task/evaluator 的安全 `skydiscover:<path>` ref resolution、active-reference blockers，以及不访问网络的 show。
- SkyDiscover Python evaluator 已支持通过 subprocess wrapper 执行、hidden evaluator bundle staging、hidden evaluator stdout/stderr logs、structured metric/reward capture，以及可由 `cache prune --skydiscover-envs` 删除的 ALab-managed `uv` environment cache rows。
- SkyDiscover Docker evaluator 已支持 hidden bundle staging、Docker image build cache rows、与 candidate workspace 分离的 read-only evaluator bundle mount、stdout JSON metric parsing、只进入 feedback 的 evaluator artifacts JSON，以及 hidden evaluator stdout/stderr logs。
- Harbor strict single-step verifier 已支持 shared environment image/Dockerfile 和 separate verifier image/`tests/Dockerfile`，包括 strict unsupported-field rejection、literal task environment values 按 secret 处理、hidden verifier bundle staging、hidden verifier logs、从 `run:/logs/verifier/reward.{txt,json}` 解析 reward file，以及 verifier Dockerfile 的 Docker image cache rows。
- Harbor/SkyDiscover adapter-derived editable-source bootstrap 已支持：Harbor 只导入 supported task `source` path 或 fallback 到 empty source，并可在 project task text 为空时使用 `instruction.md`；SkyDiscover 只导入 benchmark initial program file/directory，且 explicit caller source 会先与 adapter-derived source 比较 tree hash，一致才 dedupe。
- 文档中 V1 command surface 已注册；当前里程碑外的 commands 会明确失败，避免意外 side effect。

## Usage

```text
alab auth init
alab project init local --config alab.project.toml --source-path . \
  --name "Example" --task "Fix the project" --key <root-key>
alab exp create --project <project_id> --name "attempt-1"
cd ./<project_id>_<exp_id>
alab status
alab help
alab run --message "try first fix"
alab submit --message "final" --summary "..." --feedback "..." --ref none
```

Runner、reward、artifact、log、environment 和 secret 设置都来自 project config file。Project initialization 会在 project record 写入后生成并只打印一次 project admin key。

CLI help 是 context-aware 的。在只有 experiment token 的 worktree 中，`alab help` 聚焦当前可用 surface。Project/root management commands 默认隐藏；直接尝试使用 unavailable command 会在产生 side effect 前以 `COMMAND_UNAVAILABLE` 失败。显式 `--key` 或 `--key-stdin` 会解锁匹配的 admin/root surface；ambient `ALAB_KEY` 不扩展 help 或 token/public command surface。

仓库还在 `skills/` 下提供 Codex-facing role skills。它们是通过 CLI 操作 ALab 的外部 runbooks，分别面向 experiment worker、project controller 和 global admin；它们不会给 ALab 增加内置 agent launcher。

## Setup

通过 `uv` 安装和运行：

```text
uv run alab help
uv run pytest
```

如果本地镜像较慢或不可用，可对当前命令临时使用官方 PyPI 源，并把 cache 放在仓库内：

```text
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest
```

当依赖下载不可用时，如果现有 Python 环境已经有 pytest 和 pydantic，也可以运行当前 tests：

```text
PYTHONPATH=src python -m pytest
```

可选的本地环境变量列在 `.env.example` 中。真实 `.env` 文件会被 ignore；不要把实际 root/admin key、experiment token 或 `secret_env` 值放入 tracked files。

真实 Docker-backed integration coverage 是 opt-in，这样默认 test suite 不会意外拉取 image。Docker 可用时，它会覆盖 Docker image command 和 shell runners、real container environment isolation 和 internal `ALAB_*` override precedence、Dockerfile build-context filtering and cache reuse、带 task/external secret injection 的 Harbor verifier execution、带 secret injection 的 SkyDiscover Docker evaluator execution，以及 Dockerfile-backed adapter images 的 real Docker image-cache reuse：

```text
ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m real_docker
```

真实 SkyDiscover Python dependency-installation coverage 也是 opt-in。它会创建真实 `uv` evaluator environment，并安装本地生成的 wheel，因此可以在不需要 network access 的情况下覆盖 dependency path：

```text
ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache uv run pytest -m real_skydiscover_python
```

Networked SkyDiscover Python dependency coverage 是单独的 opt-in 路径。它会通过 evaluator environment 从 configured Python index 安装 direct 和 transitive pure-Python dependency cases：

```text
ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m networked_skydiscover_python
```

Native/binary SkyDiscover Python dependency coverage 也是单独 opt-in。默认会从 configured Python index 安装 `orjson>=3.10,<4`，也可以通过 `ALAB_NATIVE_SKYDISCOVER_PYTHON_REQUIREMENT` 和 `ALAB_NATIVE_SKYDISCOVER_PYTHON_MODULE` 覆盖：

```text
ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m native_skydiscover_python
```

真实 SkyDiscover catalog coverage 也是 opt-in，因为它会从 network clone 官方 catalog。它会验证 exact commit pinning、无需网络的 `catalog show`，以及通过 `project init skydiscover --skip-baseline-test` 解析真实 catalog evaluator：

```text
ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=.uv-cache uv run pytest -m live_skydiscover_catalog
```

当前代码可用以下命令 lint：

```text
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run ruff check
```

GitHub Actions 会在 pull request 和推送到 `main` 时运行默认 lint 与 pytest suite。该 workflow 会把默认 pytest suite 按文件组拆开，让较慢的 CLI contract 和 smoke suites 并行执行；真实 Docker、SkyDiscover Python dependency 和 live catalog gates 仍保留为手动 `workflow_dispatch` inputs。

## Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── blueprint.md
│   ├── blueprint_cn.md
│   ├── spec_cli.md
│   ├── spec_cli_cn.md
│   ├── spec_lifecycle.md
│   ├── spec_lifecycle_cn.md
│   ├── spec_storage_auth_context.md
│   ├── spec_storage_auth_context_cn.md
│   ├── spec_project_source_experiment.md
│   ├── spec_project_source_experiment_cn.md
│   ├── spec_runners_adapters.md
│   ├── spec_runners_adapters_cn.md
│   ├── spec_observe_collaboration.md
│   ├── spec_observe_collaboration_cn.md
│   ├── spec_tests.md
│   ├── spec_tests_cn.md
│   ├── completion_audit.md
│   ├── completion_audit_cn.md
│   ├── progress.md
│   ├── progress_cn.md
│   ├── progress_pipeline.md
│   ├── progress_pipeline_cn.md
│   ├── progress_closed_gaps.md
│   ├── progress_closed_gaps_cn.md
│   ├── progress_log.md
│   └── progress_log_cn.md
├── examples/
│   └── skydiscover_circle_packing_codex/
├── skills/
│   ├── alab-experiment-worker/
│   ├── alab-project-controller/
│   └── alab-global-admin/
├── src/
│   └── alab/
├── tests/
│   ├── test_smoke.py
│   ├── test_runner_docker.py
│   ├── test_runner_harbor.py
│   └── test_runner_skydiscover.py
├── LICENSE
├── .env.example
├── pyproject.toml
├── README.md
└── README_cn.md
```

`AGENTS.md`、`CORE.md` 等 local-only agent notes 会被有意加入 `.gitignore`，不属于公开 repository layout。

## Development Workflow

使用 project-local environment 和 pinned dependencies（可用时）。保持 CLI rendering 与 command logic 分离，将 SQLite access 限定在显式 repository helpers 后面，并为主要 workflow 添加聚焦的 unit 和 integration tests。

第一个实现里程碑先让本地工作流可用，再添加较重 adapter：scaffold CLI，完成 storage/credentials/context，支持 local/Git/empty source import，运行 local runner，并完成 run/submit/observe 基础能力。Docker、Harbor、SkyDiscover Python/Docker 和 adapter-derived editable-source bootstrap 现在已经通过相同 source/runner boundary 接入。

## Documentation

- 英文文档是 canonical。
- 中文同步文档使用 `*_cn.md` 命名。
- [docs/blueprint.md](docs/blueprint.md) 保持为 overview。
- 在 [docs/progress.md](docs/progress.md) 维护当前 implementation dashboard。
- 在 [docs/progress_pipeline.md](docs/progress_pipeline.md) 维护 active implementation queue。
- 在 [docs/progress_closed_gaps.md](docs/progress_closed_gaps.md) 维护 duplicate-work guardrails。
- 在 [docs/progress_log.md](docs/progress_log.md) 保留历史 implementation journal。
- 在 [docs/completion_audit.md](docs/completion_audit.md) 跟踪 requirement-level completion evidence。
- 子系统 specs 需要与对应中文版本同步：
  - [docs/spec_cli.md](docs/spec_cli.md)
  - [docs/spec_lifecycle.md](docs/spec_lifecycle.md)
  - [docs/spec_storage_auth_context.md](docs/spec_storage_auth_context.md)
  - [docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md)
  - [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md)
  - [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md)
  - [docs/spec_tests.md](docs/spec_tests.md)

## License

项目许可证是 `GPL-3.0-or-later`；见 [LICENSE](LICENSE)。
