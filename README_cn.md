# ALab

<p align="center">
  <img src="docs/assets/readme-header.png" alt="Hand-drawn ALab virtual experiment workbench banner" width="100%">
</p>

ALab 是一个本地、agent-first 的 Python CLI 实验工作台。外部 agent 可以在 ALab 创建的隔离 Git worktree 中迭代，运行可重复 evaluation，提交最终结果，并通过明确的协作边界查看可见的历史 experiment 证据。

ALab V1 有意保持 local-only：没有 server、sync service、Web UI、内置 agent launcher 或 account system。ALab 负责本地 project records、source snapshots、experiment lifecycle、runner execution、logs、artifacts 和 visibility rules；agent 仍然是外部 CLI operator。

## Highlights

- 面向 projects、sources、experiments、runs、submissions、logs、artifacts、annotations 和 audits 的本地 CLI workbench。
- Context-aware command surface：`alab help` 和 command preflight 只显示当前 project、experiment、inspection checkout、token 或 explicit key 可使用的 commands。
- Git-backed experiment isolation：每个 experiment 是独立 branch/worktree，并有 worktree token 用于 run 和 submit。
- 可复现 project setup：project config 控制 runner、reward、artifact capture、environment、secrets、mutable paths 和 visibility。
- Runner 支持 local subprocess、Docker image/Dockerfile、Harbor verifier，以及 SkyDiscover Python/Docker evaluator。
- 协作边界，不是本地强安全隔离：root/admin key 和 experiment token 约束 CLI capability，但本地 project records 仍是 plaintext。
- Secret hygiene：不存 raw key/token；生成的 raw key 只打印一次，experiment token 留在 token file 中，`secret_env` values 不会渲染或 export。
- 开源文档集：英文为 canonical，并配套同步中文 `*_cn.md` 文档。

## Current Status

当前 V1 implementation 已可运行，并且当前 worktree 的 evidence ledger 已关闭。产品契约仍以 [docs/blueprint.md](docs/blueprint.md) 为准；详细 requirement evidence 在 [docs/completion_audit.md](docs/completion_audit.md)；当前进度和 active queue 在 [docs/progress.md](docs/progress.md) 与 [docs/progress_pipeline.md](docs/progress_pipeline.md)。

## Environment Requirements

必需：

- macOS 或 Linux。Windows 不属于 V1 acceptance testing。
- Python 3.11 或更新版本。
- Git。
- [`uv`](https://docs.astral.sh/uv/) 用于 project-local Python environment 和 locked dependency resolution。

可选：

- Docker，仅用于 Docker runner 和 Harbor/SkyDiscover Docker evaluator workflows。
- Python package index 网络访问，用于会安装依赖的 evaluator tests。
- GitHub 网络访问，用于 live SkyDiscover catalog validation。
- Codex CLI 或其他外部 agent runtime，用于 autonomous workers；ALab 本身不启动 agent。

本地 environment variables 记录在 [.env.example](.env.example)。真实 `.env` 文件会被 ignore；不要提交 root key、project admin key、experiment token 或 secret values。

## Installation

ALab 以 `alab-cli` Python package 分发，并安装 `alab` console script。等 package 发布到 Python package index 后，可直接用 pip 安装：

```sh
python -m pip install alab-cli
alab help
```

在发布前，可从 checkout 或 Git URL 安装：

```sh
python -m pip install "git+https://github.com/bebetterest/ALab.git"
```

或者，从已经 clone 的 checkout 安装：

```sh
git clone https://github.com/bebetterest/ALab.git ALab
cd ALab
python -m pip install .
alab help
```

如果需要带已安装命令的 editable local development：

```sh
python -m pip install -e .
alab help
```

如果更希望使用隔离 CLI tool environment，`uv` 也可以安装同一个 console script：

```sh
uv tool install --editable .
alab help
```

如果 `pip` 或 `uv` 把命令安装到了不在 `PATH` 的目录，请把提示中的 script directory 加入 shell path。

做 repository development 和 locked local verification 时，使用 checkout environment：

```sh
uv sync --locked
uv run --locked alab help
```

运行默认 validation suite：

```sh
uv run --locked pytest -q
uv run --locked ruff check
```

如果本地 package mirror 较慢或不可用，可对当前命令使用官方 Python index：

```sh
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked pytest -q
```

如果无法下载依赖，但当前 Python environment 已有 required test dependencies，也可以直接运行 source tree：

```sh
PYTHONPATH=src python -m pytest -q
```

## Quick Start

这个 local runner 示例会在仓库下创建一个隔离 ALab home，从一个小 Python source tree 初始化 project，创建一个 experiment，运行 evaluation，并提交结果。

下面的命令默认已安装 `alab`。如果只在 checkout 中工作，在仓库内可把 `alab` 替换为 `uv run --locked alab`；从 experiment worktree 中运行时，可替换为 `uv run --project /absolute/path/to/ALab --locked alab`。

创建 demo source 和 config：

```sh
mkdir -p .alab-demo/source
cat > .alab-demo/source/main.py <<'PY'
print("reward=1.0")
PY

cat > .alab-demo/alab.project.toml <<'TOML'
[runner]
type = "local"
command = ["python", "main.py"]
timeout_seconds = 60
working_directory = "."
env_mode = "sanitized"

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"
TOML
```

初始化 ALab home。Root key 只会打印一次：

```sh
ALAB_HOME="$PWD/.alab-demo/home" alab auth init
```

使用打印出的 root key 初始化 project：

```sh
ALAB_HOME="$PWD/.alab-demo/home" alab project init local \
  --config .alab-demo/alab.project.toml \
  --source-path .alab-demo/source \
  --name "Demo" \
  --task "Keep the reward output passing" \
  --key <root-key>
```

创建 experiment。Local agent bootstrap 默认允许 public experiment creation：

```sh
ALAB_HOME="$PWD/.alab-demo/home" alab exp create \
  --project <project-id> \
  --name "attempt-1"
```

进入输出中的 worktree path，运行 evaluator，并在 passed run 后 submit：

```sh
cd <worktree-path>
ALAB_HOME="/absolute/path/to/ALab/.alab-demo/home" alab status
ALAB_HOME="/absolute/path/to/ALab/.alab-demo/home" alab run --message "baseline demo run"
ALAB_HOME="/absolute/path/to/ALab/.alab-demo/home" alab submit \
  --message "final demo candidate" \
  --summary "The demo candidate prints a parseable reward." \
  --feedback "The latest run passed with reward 1.0." \
  --ref none
```

常用后续 commands：

```sh
alab help
alab observe experiments list
alab observe runs list --exp <exp-id>
alab observe experiments best
```

## Core Concepts

- **Home**：本地 ALab state root，包含 SQLite records、config、caches、backups 和 project storage。
- **Project**：task、goal、config、source registry、validation records、visibility policy 和 project admin boundary。
- **Source**：从 local path、Git repo、empty source、Harbor task source 或 SkyDiscover initial program 导入的 immutable snapshot。
- **Experiment**：绑定到一个 source 和一个 config version 的隔离 Git branch/worktree。
- **Run**：针对某个 experiment commit 的一次 evaluator execution，包含 status、reward、logs、artifacts 和 warning codes。
- **Submit**：用 final summary、feedback、final run、final commit 和 explicit refs 关闭 experiment。
- **Inspection checkout**：只读 checkout，用于 observe/export scoped experiment evidence，不会变成 submit-capable。

## Configuration

Project behavior 由 TOML config 控制：

- `[runner]`：runner type、command/shell、working directory、timeout、Docker fields、Harbor task refs 或 SkyDiscover task refs。
- `[reward]`：reward type 和 primary metric。支持 `exit_code`、`file`、`stdout_regex`、`harbor`、`skydiscover`。
- `[artifacts]` 和 `[logs]`：captured output roots、glob patterns 和 byte limits。
- `[env]` 和 `[secret_env]`：显式 environment injection。Secret values 是本地 plaintext，但不渲染或 export。
- `[mutable]`：experiment 在 run 或 submit 时允许修改的 paths。
- Visibility/public bootstrap policy：控制 experiments 如何查看 prior work，以及是否允许本地 no-key experiment creation。

详细契约见 [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md)、[docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md) 和 [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md)。

## Examples

参见 [examples](examples/) 中的 runnable example matrix。当前 examples 覆盖
local scoring loop、带 artifact export 的 Dockerized 诊所订单履约计划器、Harbor
hidden-verifier incident classifier、协作式 incident triage lifecycle workflow，
以及 SkyDiscover circle-packing Codex single-worker protocol。

仓库还在 [skills](skills/) 下提供 Codex-facing role skills。它们是通过 CLI 操作 ALab 的外部 runbooks，分别面向 experiment worker、project controller 和 global admin；它们不会给 ALab 增加内置 agent launcher。

## Testing And Development

默认检查：

```sh
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked pytest -q
UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run --locked ruff check
```

Opt-in integration gates 不属于默认 suite：

```sh
ALAB_RUN_REAL_DOCKER=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m real_docker
ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m real_skydiscover_python
ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m networked_skydiscover_python
ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m native_skydiscover_python
ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 UV_CACHE_DIR=.uv-cache UV_DEFAULT_INDEX=https://pypi.org/simple uv run pytest -m live_skydiscover_catalog
```

说明：

- `uv.lock` 会被 tracked，因为 CI 和本地 validation 使用 `uv run --locked`。
- 本地 cache/output paths 应保持 ignored（`.uv-cache/`、`.pytest_cache/`、`.ruff_cache/`、`.alab-demo/`、`.env`）。
- GitHub Actions 会在 pull request 和推送到 `main` 时运行默认 lint 与 pytest suite；真实 Docker 和 live/networked SkyDiscover gates 仍是 manual workflow inputs。
- 推送到 `main` 时会检查 PyPI 是否已有当前 `pyproject.toml` package version；如果缺少该精确版本，CI 会通过 PyPI Trusted Publishing 构建并发布，否则跳过发布。
- 首次自动发布前，PyPI `alab-cli` project 需要信任 repository `bebetterest/ALab`、workflow `ci.yml` 和 environment `pypi`。

## Security And Data Model

ALab V1 是本地协作边界，不是 multi-user security product：

- Raw root/admin keys 只在 creation/regeneration 时打印一次。
- Raw experiment tokens 会写到 token files，不会打印。
- 存储 credential verifiers，不存 raw credential secrets。
- Project records 是本地 plaintext SQLite/filesystem data。
- `secret_env` values 是本地 plaintext；配置后会从 rendered logs 中 redacted，config commands 不会导出。
- Artifact exports 是精确捕获的 bytes，不会自动 redacted。

## Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── assets/
│   │   └── readme-header.png
│   ├── README.md
│   ├── README_cn.md
│   ├── blueprint.md
│   ├── blueprint_cn.md
│   ├── completion_audit.md
│   ├── completion_audit_cn.md
│   ├── progress.md
│   ├── progress_cn.md
│   ├── progress_pipeline.md
│   └── progress_pipeline_cn.md
├── examples/
│   ├── README.md
│   ├── README_cn.md
│   ├── collaboration_observe_lifecycle/
│   ├── docker_file_reward_artifacts/
│   ├── harbor_verifier_minimal/
│   ├── local_agent_scoreboard/
│   └── skydiscover_circle_packing_codex/
├── skills/
│   ├── alab-experiment-worker/
│   ├── alab-project-controller/
│   └── alab-global-admin/
├── src/
│   └── alab/
├── tests/
│   ├── test_smoke.py
│   ├── test_cli_contract.py
│   ├── test_runner_docker.py
│   ├── test_runner_harbor.py
│   └── test_runner_skydiscover.py
├── LICENSE
├── .env.example
├── pyproject.toml
├── uv.lock
├── README.md
└── README_cn.md
```

`AGENTS.md`、`CORE.md` 等 local-only agent notes 会被有意加入 `.gitignore`，不属于公开 repository layout。

## Documentation

- 英文文档是 canonical。
- 中文同步文档使用 `*_cn.md` 命名。
- [docs/README.md](docs/README.md) 说明文档结构和阅读顺序。
- [docs/blueprint.md](docs/blueprint.md) 是 V1 product overview。
- [docs/spec_cli.md](docs/spec_cli.md)、[docs/spec_storage_auth_context.md](docs/spec_storage_auth_context.md)、[docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md)、[docs/spec_lifecycle.md](docs/spec_lifecycle.md)、[docs/spec_runners_adapters.md](docs/spec_runners_adapters.md)、[docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md) 和 [docs/spec_tests.md](docs/spec_tests.md) 定义 subsystem contracts。
- [docs/progress.md](docs/progress.md)、[docs/progress_pipeline.md](docs/progress_pipeline.md)、[docs/progress_closed_gaps.md](docs/progress_closed_gaps.md) 和 [docs/progress_log.md](docs/progress_log.md) 跟踪 current state、active queues、closed gaps 和 history。
- [docs/completion_audit.md](docs/completion_audit.md) 跟踪 requirement-level evidence。

## Contributing

- 改动应保持 scoped，并与 blueprint/spec contracts 对齐。
- 先更新英文 docs，再同步匹配的中文 `*_cn.md` 文件。
- 新行为要增加 focused tests，并在 PR 前运行相关 pytest/ruff commands。
- 不要提交真实 `.env` 文件、raw keys、experiment tokens、generated caches、本地 ALab homes 或 private runner outputs。

## License

项目许可证是 `GPL-3.0-or-later`；见 [LICENSE](LICENSE)。
