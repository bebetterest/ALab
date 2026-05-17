# ALab

ALab 是一个本地、agent-first 的 Python CLI 实验工作台。它面向这样的工作流：外部 agent 在 ALab 创建的 Git worktree 中工作，运行评估，提交最终结果，并通过明确的协作可见性规则查看历史 experiment。

项目当前处于蓝图阶段。还没有可运行 CLI、package scaffold 或依赖环境。规范性总览是 [docs/blueprint.md](docs/blueprint.md)，`docs/` 下包含同步的子系统 specs，中文版本使用 `*_cn.md` 命名。

## Highlights

- Local-only V1：无 server、sync service、Web UI、内置 agent launcher 或 account system。
- Agent-first CLI：默认和持久化输出都是 plain text；Rich output 只能通过 `--output rich` 对单次命令启用。
- 协作边界，不是本地强安全隔离：root/admin key 和 experiment token 用于 CLI 权限控制，project records 是本地明文数据。
- Secret hygiene：不存 raw key/token；`secret_env` 值是本地 plaintext，但不渲染或 export；configured secrets 会从 logs 中 redacted。Artifact export 是精确捕获的 bytes，不会自动 redacted。
- Project/experiment model：project 定义 task、source、runner、reward、artifact、mutable scope 和 visibility；experiment 是隔离 Git branch 和 worktree。
- Immutable source snapshots：local、Git、empty、Harbor、SkyDiscover input 都表示为 canonical project repository 中的 source ref。
- Multi-source projects：一个 project 可以保留多个 source；每个 active config 有一个 default source；每个 experiment 创建时绑定且只绑定一个 source。
- 分阶段实现：核心里程碑先做 local/Git/empty source 和 local runner；Docker、Harbor、SkyDiscover 作为 V1 一等 adapter 后续接入。
- Implementation model：计划中的 stack 是 Typer CLI handlers 调用 service workflows，显式 `sqlite3` repositories，Pydantic boundary models，以及只消费 command result objects 的 renderer。
- Baseline validation：project init 和 runtime-affecting config change 默认运行 baseline test。
- Public bootstrap：project 默认允许本地 no-key experiment creation，可从 source 或可见 open/closed experiment 创建，public from-experiment inheritance 受 source experiment visibility bound 限制，方便 agent 使用，但不授予 project-management 或 observe-history access。
- Inspection checkout：只读 CLI context 可通过 scoped token observe/export，不会变成 submit-capable experiment。
- Explicit lifecycle model：archive/unarchive 是幂等可逆状态，remove 是带 dry-run blocker 的 audited archive-first deletion，worktree remove 可调和已经缺失的 registered path，prune/gc 只清理 non-authoritative data。
- Runner plan：V1 规定 local、只支持 `default|none` 网络的 explicit-field Docker、Harbor strict single-step Linux subset、SkyDiscover Docker evaluator、SkyDiscover Python evaluator 的 contract。

## Planned Usage

最终 CLI 预期类似：

```text
alab auth init
alab project init local --config alab.project.toml --source-path . \
  --name "Example" --task "Fix the project" --key <root-key>
alab project validate --project <project_id> --key <root-or-admin-key>
alab exp create --project <project_id> --name "attempt-1"
cd ./<project_id>_<exp_id>
alab status
alab run --message "try first fix"
alab submit --message "final" --summary "..." --feedback "..." --ref none
```

Runner、reward、artifact、log、environment 和 secret 设置都预期来自 project config file。这些命令是设计目标，目前还不是可执行命令。Project initialization 预期会在 project record 写入后生成并只打印一次 project admin key。

## Repository Structure

```text
.
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
│   └── spec_tests_cn.md
├── README.md
└── README_cn.md
```

`AGENTS.md`、`CORE.md` 等 local-only agent notes 会被有意加入 `.gitignore`，不属于公开 repository layout。

未来实现预计会添加 `src/alab/`、`tests/`、`pyproject.toml` 和 `LICENSE`。

## Development Workflow

实现开始前，开发工作应聚焦于保持蓝图 decision-complete 并同步中英文文档。实现开始后，应使用 project-local environment 和 pinned dependencies，保持 CLI rendering 与 command logic 分离，将 SQLite access 限定在显式 repository classes 后面，并为主要 workflow 添加聚焦的 unit 和 integration tests。

第一个实现里程碑应先让本地工作流可用，再添加较重 adapter：scaffold CLI，完成 storage/credentials/context，支持 local/Git/empty source import，运行 local runner，并完成 run/submit/observe 基础能力。Docker、Harbor、SkyDiscover 随后通过蓝图已定义的 runner/source adapter interface 接入。

## Documentation

- 英文文档是 canonical。
- 中文同步文档使用 `*_cn.md` 命名。
- [docs/blueprint.md](docs/blueprint.md) 保持为 overview。
- 子系统 specs 需要与对应中文版本同步：
  - [docs/spec_cli.md](docs/spec_cli.md)
  - [docs/spec_lifecycle.md](docs/spec_lifecycle.md)
  - [docs/spec_storage_auth_context.md](docs/spec_storage_auth_context.md)
  - [docs/spec_project_source_experiment.md](docs/spec_project_source_experiment.md)
  - [docs/spec_runners_adapters.md](docs/spec_runners_adapters.md)
  - [docs/spec_observe_collaboration.md](docs/spec_observe_collaboration.md)
  - [docs/spec_tests.md](docs/spec_tests.md)

## License

计划中的项目许可证是 `GPL-3.0-or-later`。License 文件尚未添加。
