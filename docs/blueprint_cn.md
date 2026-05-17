# ALab V1 蓝图

本文档是 ALab V1 的中文同步总览。英文版 [blueprint.md](blueprint.md) 是规范性来源；子系统实现契约位于下列 spec。任何子系统细节变更，都应先更新英文 spec，再在同一次变更中更新对应的中文 `*_cn.md` 文件。

## 1. 文档地图

- CLI、全局参数、输出、命令契约和错误：[spec_cli.md](spec_cli.md)，中文同步版 [spec_cli_cn.md](spec_cli_cn.md)
- Storage、credential、auth、context、migration 和 config persistence：[spec_storage_auth_context.md](spec_storage_auth_context.md)，中文同步版 [spec_storage_auth_context_cn.md](spec_storage_auth_context_cn.md)
- Project、source、experiment、worktree、run 和 submit 生命周期：[spec_project_source_experiment.md](spec_project_source_experiment.md)，中文同步版 [spec_project_source_experiment_cn.md](spec_project_source_experiment_cn.md)
- Archive、unarchive、remove、restore、repair、revoke、prune 和 lifecycle audit 规则：[spec_lifecycle.md](spec_lifecycle.md)，中文同步版 [spec_lifecycle_cn.md](spec_lifecycle_cn.md)
- Runner、reward、log、artifact、Docker、Harbor 和 SkyDiscover adapter 契约：[spec_runners_adapters.md](spec_runners_adapters.md)，中文同步版 [spec_runners_adapters_cn.md](spec_runners_adapters_cn.md)
- Observe、协作可见性、log、tag、artifact 和 annotation：[spec_observe_collaboration.md](spec_observe_collaboration.md)，中文同步版 [spec_observe_collaboration_cn.md](spec_observe_collaboration_cn.md)
- V1 验证计划和 acceptance coverage：[spec_tests.md](spec_tests.md)，中文同步版 [spec_tests_cn.md](spec_tests_cn.md)

## 2. 产品定义

ALab 是一个本地、agent-first 的 Python CLI 实验工作台。外部 agent 在 ALab 创建的 Git worktree 中工作，通过 `alab` 创建尝试、提交迭代、运行评估、提交最终结果、查看可见历史、导出 artifact、编写 annotation。

ALab 负责 project 结构和本地记录。V1 不启动 agent、不调度 agent、不选择 prompt、不运行搜索循环、不托管服务，也不跨机器同步数据。

核心对象：

- Project：任务定义、canonical Git 仓库、source 版本、runner 配置、reward 策略、mutable path 策略、visibility 策略、validation 记录、credential 和 experiment。
- Source：导入到 project 仓库中的不可变代码快照，通过 `alab/source/<source_id>` 引用。
- Experiment：一次具名尝试，包含 Git branch、worktree、scoped token、tag、run 记录、artifact、annotation 和可选 final submission。
- Run：对某个 commit 的评估，包含 log、status、reward、metric、artifact、runner metadata 和 config version。
- Project validation：project 级 baseline run，用于证明所选 source、runner、reward、artifact、environment、timeout 和 policy 配置可以执行。
- Annotation：挂在 experiment、run、artifact、repo path 或 repo line range 上的 revisioned note。

V1 成功标准是：本地用户可以初始化 ALab、创建 project、验证 baseline、从可复用 source 版本创建 experiment，让 agent 在不反复输入 project key 的情况下 run/submit，并能按照明确的协作可见性规则查看本地历史。

Project initialization 在写入 project record 时始终创建一个 project admin key，并且只显示一次 raw admin key。Root/admin 用户可以通过 audit commands 查看 sanitized lifecycle audit event。

## 3. V1 边界

V1 不包含：

- 托管服务、账号系统、多用户 server、原生 Web UI、远程数据库、云对象存储或跨机器同步。
- 内置 LLM provider 集成。
- Agent 调度、自动搜索或 agent hiring。
- 同一 OS 账号或同一文件系统内不同用户之间的强安全隔离。
- 加密 SQLite、加密 record/blob storage、per-record DEK、grant file、public grant、token rewrap 或基于加密的 revocation。
- 除 Git scope 检查、干净临时 runner 目录和可选 Docker 执行之外的细粒度 OS sandbox。
- JSON 或 XML 输出。renderer 边界需要允许未来扩展，但 V1 默认只暴露 `text`，`rich` 只能作为单次命令 override。
- 任意 byte 或 character span annotation。
- Docker Compose、Kubernetes 或远程 container executor。
- root/admin key 丢失后的恢复。
- Windows host 支持。V1 只正式支持 macOS 和 Linux host。

安全说明：

- V1 authorization 是服务本地 agent workflow 的协作边界。
- Project 数据、任务文本、log、summary、feedback、tag、annotation、捕获的 artifact 和 `secret_env` 值都以本地明文 SQLite row 或明文文件存储。
- ALab 不得在创建/输入后再次打印 raw key、token 或 `secret_env` 值。
- Credential verifier 存储为 salted HMAC hash，不存 raw secret。
- 如果用户需要抵御其他本地用户读取数据，必须依赖 OS 文件权限或未来的加密存储模式。

## 4. 运行形态和技术栈

ALab 安装为本地 Python CLI：`alab`。

V1 技术栈：

- Python 3.11 或更新版本。
- `uv` 用于项目和依赖管理。
- Typer 用于命令路由和参数解析。
- Rich 安装为依赖，但绝不作为默认输出路径。
- Pydantic 用于严格模型验证。
- 标准库 SQLite 用于本地 index 和明文 records。
- 标准库 `secrets`、`hashlib`、`hmac` 用于 credential 生成和验证。
- `tomli-w` 用于 TOML 写入。
- `pathspec` 用于 Git-ignore-style matching。
- pytest 用于测试。
- Git CLI subprocess 用于 repository、branch、commit、worktree 和 checkout 操作。
- Docker CLI 作为 Docker、Harbor、SkyDiscover Docker runner 的可选运行时依赖。

支持 host 为 macOS 和 Linux。Windows 不进入 V1 acceptance testing。

实现架构：

- Typer 只是 CLI 边界。它负责解析 argv、预扫描 global options、处理 stdin key input，然后调用 service-layer handler。
- Service-layer handler 负责业务 workflow、lock acquisition、validation sequencing、Git 操作、runner orchestration 和 lifecycle decision。
- Repository class 通过显式 transaction 和 typed query method 管理 Python `sqlite3` access。V1 不使用 ORM。
- Pydantic model 在模块边界校验 TOML input、canonical JSON field、command result、runner record 和 renderer input。
- Renderer 只消费 structured result object。它不得重新查询 storage、执行 authorization check，或添加 result object 中不存在的字段。
- 未来实现应采用分层 package 结构：CLI routing、service workflows、repositories、Pydantic models、renderers、Git helpers、storage/migrations、runners、adapters 和 tests 分别保持清晰边界。

## 5. ALab Home 和文件

默认 ALab home：

```text
~/.ALab
```

Home 解析优先级：

1. `--home <path>`
2. `ALAB_HOME`
3. `~/.ALab`

Canonical filesystem layout：

```text
~/.ALab/
├── alab.db
├── config.toml
├── backups/
├── project-workspaces/
│   └── <project_id>/
│       └── .alab/
│           └── context.json
├── projects/
│   └── <project_id>/
│       ├── repo.git/
│       └── artifacts/
│           ├── blobs/
│           └── logs/
├── sources/
│   └── skydiscover/
├── cache/
│   ├── docker-images/
│   └── skydiscover-python-envs/
└── tmp/
```

V1 没有 `records/` 目录。SQLite 是结构化 record 的 authoritative store。Log 和 artifact bytes 由文件承载，并由 SQLite 引用。

`auth init` 生成稳定的 `home_id`，写入 SQLite，并写入每个 `.alab/context.json` marker。Context repair 必须验证 `home_id` 后才接受 marker。

`project-workspaces/` 下的 project workspace directory 是 marker-only project control context。它们不是 source checkout，也绝不是默认 experiment worktree。`exp create` 省略 `--path` 时，ALab 在 command cwd 下创建 `./<project_id>_<exp_id>`，并注册其 resolved path。Command cwd 可以是 project control context，但不是必须；任意通过 realpath、empty-directory 和 context nesting check 的 cwd 都有效。Custom experiment 和 inspection path 也可以位于 ALab home 之外，但必须通过同样的 checks。

## 6. CLI 和输出摘要

Global options 可以放在 subcommand 前或后。CLI 必须在 context detection、migration、config loading、credential lookup 或 command-specific parsing 前预扫描 global options：

```text
alab [--home <path>] [--output text|rich] [--key <secret>] [--key-stdin] <command> [args]
```

`--key` 与 `--key-stdin` 冲突；只有二者都不存在且命令需要 root/admin authorization 时才读取 `ALAB_KEY`。Public 或 optionally authorized 命令不得用 `ALAB_KEY` 静默提升输出权限。Global option pre-scan 在 standalone `--` 处停止。

`text` 是默认输出，也是唯一可持久化输出格式。它是严格 key-value object 格式：每个 object block 以 `object: <type>` 开头，字段渲染为 `field: value`，多行文本在 `field:` 后使用缩进 block，list 使用 repeated labeled lines，重复 object 之间用一个空行分隔。Warning 在主结果后以 `object: warning` 渲染。`rich` 使用同一份 structured result data 进行不同渲染，只能通过 `--output rich` 对单次命令启用。

每个 stable error code 都映射到唯一 numeric exit code。所有 `*_NOT_FOUND` code exit `2`；`PROJECT_INVALID` exit `4`；已保存 runner 或 validation result error 时 exit `1`；只有无法保存目标 record 的 failure 才是 system/internal exit `5`。

`ALAB_DEBUG=1` 只影响 internal/system error。它可以打印完整 stack trace，但不得打印 locals、environment map、raw key、raw token、secret value 或 hidden asset content。

所有 ALab object id 参数在 V1 都要求完整 id。Git commit selector 是唯一可以使用 full 或 unambiguous abbreviated SHA 的值。时间过滤选项只接受带 `Z` 或显式数字 offset 的 RFC 3339 timestamp，并在内部归一化为 UTC `Z`。

## 7. Source 和 Experiment 方向

Source 是 `alab/source/<source_id>` 下的不可变 Git snapshot ref。一个 project 可以包含多个 source；一个 active project config 只命名一个 default source；每个 experiment 创建时只绑定一个 source。V1 先实现 local path、remote Git 和 empty source import。Git submodule/gitlink 在 V1 中以 `SOURCE_INVALID` 拒绝；用户必须先 vendor 或展开 submodule content 再 import。Harbor 和 SkyDiscover adapter 后续通过同一 source 和 runner 边界接入。

在 `project init` 期间，如果 init 命令提供了一个 effective default source origin，输入 config 可以省略 `source.default_source_ref`。ALab 先 staging project repository 和 source snapshot，计算 canonical source ref，在一个 SQLite transaction 中写入 project/source/config/admin credential rows，并且只在 transaction 成功后打印 raw admin key。如果 input config 已包含 `source.default_source_ref`，该值会被视为 expected canonical ref；如果它与 staged source ref 不匹配，则以 `CONFIG_INVALID` 失败，不会被静默覆盖。

Adapter project init 可以从 Harbor 或 SkyDiscover task 派生 editable source。如果调用者也显式提供 editable source，ALab 会比较 canonical source tree hash。内容相同则正常 dedupe；内容不同则 source conflict 失败，因为 V1 不会在 project initialization 期间静默选择两个不同 editable source 中的一个。

Public no-key experiment creation 和 public inline source import 默认启用。Public no-key checkout 和 observe history 不允许。历史查看必须发生在带有效 token 的 experiment 或 inspection context 中。Public no-key `exp create --from-exp` 允许从 visible open/closed experiment 进行 source inheritance，支持 `final`、`latest`、`best` 和 source experiment branch 可达 commit SHA selector。对 no-key caller，visibility 是当前 project public inheritance policy 与 source experiment stored visibility upper bound 的交集；这可以防止 public inheritance 绕过 source experiment 创建时做出的 experiment-level visibility narrowing。Public no-key remote Git import 可以使用现有的 non-interactive Git credential helper，必须禁用 prompt，并在 helper 可用或被使用时渲染稳定 warning。Harbor 和 SkyDiscover project init 不接受 `--source-ref`；新的 adapter project 使用 path/Git/empty explicit source 或 adapter-derived editable source。

Project、source 和 experiment archive 都是可逆状态变更。Project archive 在存在 active project、validation、source import、run、submit、worktree maintenance 或 maintenance lock 时会被阻止。三者都支持 unarchive。Archive 和 unarchive command 是幂等的；目标已经处于请求状态时不写重复 audit event。Project 和 experiment unarchive 会恢复 pre-archive status。永久删除是单独的 audited lifecycle operation，定义在 [spec_lifecycle.md](spec_lifecycle.md)，hard remove command 支持 dry-run dependency check，并在不修改数据的情况下渲染 blockers。Project remove 和 experiment remove 是 target 自身 archived 之后的 explicit whole-tree cascade operations；source remove 因 config version 是 immutable reproducibility record 而保持严格。

Experiment worktree 和 inspection checkout 可由 root/admin maintenance command remove，支持 dry-run，并通过 trash-staged filesystem deletion 删除。如果 registered filesystem path 已经被 ALab 外部删除，remove command 会调和 registered state、revoke token 并写 audit event，而不是要求无法完成的 repair。Worktree restore 在用户提供的 path checkout experiment branch HEAD，revoke 旧 worktree token，并向恢复后的 worktree 写入新 token。Marker-only project control context 可以包含同一 project 的 experiment 和 inspection context；cross-project nesting 以及任何位于 experiment 或 inspection context 内的 nesting 都被拒绝。

## 8. Runner 和 Adapter 方向

核心 V1 先实现 local/Git/empty source 和 local runner。Docker、Harbor、SkyDiscover 之后通过同一 runner/source adapter contract 接入。

Adapter 决策：

- Docker runner 使用显式 whitelist 配置面：image 或 dockerfile plus context、network `default|none`、build args、build target、platform、container user、CPU limit 和 memory limit。Host networking 在 V1 不支持，也不属于计划中的 Docker surface。V1 拒绝 Docker Compose、raw Docker argument passthrough、privileged mode 和 extra host mounts。Docker-backed runner 不继承 host environment，只接收 `[env]`、`[secret_env]` 和 ALab internal variables。缺失的 `runner.image` 会自动 pull。Dockerfile build context 遵循 `.dockerignore`，cache key 包含 Dockerfile content、`.dockerignore` 和 effective filtered build context。
- Harbor 支持 single-step Linux task、shared verifier、separate verifier 和安全的 task-relative `source` import。它拒绝 Windows task、multi-step task、Docker Compose、GPU、MCP、external service、raw Docker passthrough、task-declared host mount 和 placeholder value。
- Harbor separate verifier 支持 image 或 `tests/Dockerfile`；verifier workspace mount 是临时且可写的；hidden verifier logs 仅 admin 可见。
- SkyDiscover 在 ALab V1 中只作为 evaluator。ALab 不运行 SkyDiscover search loop。
- SkyDiscover source precedence 是显式 `--source-*` 优先；否则在存在 benchmark initial program 时导入 initial program；如不存在，则 init 失败并要求显式 source。缺失 catalog 或缺失 `skydiscover:<path>` 绝不触发自动 network update。只导入 initial file 或 directory。
- SkyDiscover Python evaluator support 属于完整 V1，通过 ALab wrapper subprocess 和 `uv` environment cache 实现。它不是 OS sandbox。Dependency installation 可以使用默认网络；environment cache key 包含 dependency file hashes、platform 和 Python version。
- Source-dependent runner paths 在 config time 检查安全形态，在 baseline/run 时检查是否存在。Failed runner exits、reward parsing errors 和 timeouts 在存在 result record 时仍尽力 capture logs 和 artifacts。

## 9. 实现里程碑

Milestone 1：documentation and scaffold。

- 保持本总览和所有子系统 spec 的中英文同步。
- 添加 README、中文 README、license、Python project scaffold、no-op CLI skeleton、renderer boundary 和项目工具。

Milestone 2：storage、credentials、context。

- 实现 home resolution、SQLite WAL storage、migration、backup policy、lifecycle audit event 和 audit command、root/admin credential、experiment token、path registry、context marker、context repair、secret value 和 lock。

Milestone 3：project/source/local runner。

- 实现 project init/config/status/validate、local/Git/empty source、experiment create/archive/unarchive/remove/checkout/worktree maintenance、mutable/visibility policy check、local runner、exit-code reward、log、artifact、run 和 submit。

Milestone 4：observe and collaboration records。

- 实现 observe commands 和 aliases、filter、pagination、best ranking、log、tag、annotation 和 artifact export。

Milestone 5：Docker、Harbor、SkyDiscover。

- 实现 Docker runner、Harbor strict subset、SkyDiscover catalog pinning、SkyDiscover Docker evaluator，以及带 `uv` environment cache 的 SkyDiscover Python evaluator。

## 10. References

Planning references checked on 2026-05-16：

- Git worktree documentation: https://git-scm.com/docs/git-worktree
- Git ignore documentation: https://git-scm.com/docs/gitignore
- Harbor task documentation: https://www.harborframework.com/docs/tasks
- Harbor multi-step task documentation: https://www.harborframework.com/docs/tasks/multi-step
- Harbor Windows task documentation: https://www.harborframework.com/docs/tasks/windows-container-support
- SkyDiscover README and evaluator formats: https://github.com/skydiscover-ai/skydiscover
- uv documentation: https://docs.astral.sh/uv/
- Typer documentation: https://typer.tiangolo.com/
- Pydantic documentation: https://docs.pydantic.dev/latest/
- pathspec package: https://pypi.org/project/pathspec/
- Docker none network driver documentation: https://docs.docker.com/engine/network/drivers/none/
