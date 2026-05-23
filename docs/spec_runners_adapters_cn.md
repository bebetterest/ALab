# ALab V1 Runner、Reward、Log、Artifact 和 Adapter 规格

本文档是 [spec_runners_adapters.md](spec_runners_adapters.md) 的中文同步版。英文版是规范性来源。

## 1. Runner Contract

所有 runner 实现同一个 contract。

Inputs：

- Project id。
- Experiment id 或 validation id。
- Config version。
- Commit sha。
- Temporary `workspace` path。
- Temporary `run_dir` path。
- Temporary `hidden_dir` path。
- Environment map。
- Secret environment map。
- Timeout。
- Artifact config。
- Reward policy。

Outputs：

- Status。
- Exit code when available。
- Started/ended timestamps。
- Stdout/stderr byte streams。
- Reward extraction result。
- Metrics map。
- Artifact candidates。
- Failure reason。
- Admin-only hidden log references。

Invariants：

- Runner 永不 mutate experiment worktree。
- Runner 在 temporary clean checkout 上执行。
- Runner 可写 `workspace` 和 `run_dir`；capture 后这些写入被丢弃。
- Runner stdin closed。Local subprocess 使用 `DEVNULL`；Docker-backed runner non-interactive。
- Hidden validation assets 和 raw hidden verifier/evaluator logs 必须写在 `hidden_dir` 或 workspace/run_dir 外的 adapter staging path。
- Timeout 时 ALab 终止 process/container，并仍尝试 best-effort capture。
- 不同 experiments 可并发运行；同一 experiment 不可并发 run/submit。

Config-dependent path validation：

- Config schema validation 检查 runner、reward、artifact、Dockerfile 和 context paths 的语法、允许 root，以及 normalize 后不得 escape repository 或 runtime root。
- Schema validation 不要求 `runner.working_directory`、`reward.path`、artifact globs、`runner.dockerfile` 或 `runner.context` 等 source-dependent paths 存在于每个未来 source snapshot。
- Missing source-dependent paths 在存在 validation 或 run record 时记录为 saved baseline/run failures。它们按失败子系统使用 `RUNNER_ERROR`、`REWARD_PARSE_ERROR` 或 artifact capture statuses，而不是静默改写 config。

## 2. Runtime Directories

Temporary runtime directories：

```text
~/.ALab/tmp/<project_id>/<operation_id>/
├── workspace/
├── run/
├── hidden/
└── home/
```

规则：

- `workspace/` 是 runner 使用的 clean editable checkout。
- `run/` 是 runner output directory，可作为 `run:` artifact root。
- `hidden/` 保留给 hidden validation assets、verifier/evaluator bundles、raw hidden logs。
- `hidden/` 不是 valid artifact root，绝不能通过 token-scoped output 暴露。
- `home/` 是 local runner `env_mode = "sanitized"` 使用的 temporary HOME。
- Temporary dirs 在 command running 时可含 plaintext checkout/log/artifact。
- Capture 后 ALab 移除 temporary dirs，除非未来增加显式 debug retention flag。`ALAB_DEBUG=1` 本身不保留。

## 3. Environment Injection

Effective runner environment：

1. 按 runner type 和 `env_mode` 选择 inherited environment；
2. `[env]`；
3. `[secret_env]`；
4. ALab internal variables。

ALab internal variables 始终注入并覆盖之前值：

```text
ALAB_PROJECT_ID=<project_id>
ALAB_EXP_ID=<exp_id or empty for validation>
ALAB_RUN_ID=<run_id or validation_id>
ALAB_CONFIG_VERSION=<version>
ALAB_WORKSPACE=<workspace path inside runner context>
ALAB_RUN_DIR=<run_dir path inside runner context>
```

规则：

- 值在 operation 期间固定。
- 不从 user config 读取。
- Local、Docker、Harbor、SkyDiscover runner 都必须有这些变量。
- Docker-backed runner 使用 container-visible paths 作为 `ALAB_WORKSPACE` 和 `ALAB_RUN_DIR`。
- Docker、Harbor 和 SkyDiscover Docker runners 不继承 host environment variables；它们只接收 `[env]`、`[secret_env]` 和 ALab internal variables。
- `ALAB_KEY` 等 ALab credential variables 在 runner execution 前始终从 inherited environment 中剔除，即使 `env_mode = "full"` 也是如此。
- Runner 绝不接收 `.alab/context.json` 或 `.alab/token`；temporary workspace 是 clean code checkout，不是 submit-capable ALab context。

## 4. Local Runner

规则：

- `runner.command` 以 argv 执行，不通过 shell。
- `runner.shell` 在支持的 V1 host 上显式使用 `/bin/sh -c <shell>`。
- `runner.shell` 在 V1 只由 local runner 和 Docker runner shell mode 支持。Harbor、SkyDiscover Docker 和 SkyDiscover Python runner 拒绝用户 `runner.shell`，因为 adapter verifier/evaluator commands 由 adapter contract 管理。
- Local runner workspace containment checks 使用 normalized path ancestry，而不是 string-prefix matching；因此带有 workspace 名称前缀的 sibling paths 仍会被判定为 escape 并失败。
- `env_mode = "sanitized"` 只继承存在的 `PATH`、`LANG`、`LC_*`、`TZ`、`TMPDIR`，并把 `HOME` 设置为 temporary `home/` directory。
- ALab 在启动 local runner process 前创建 sanitized temporary `home/` directory。
- `env_mode = "full"` 继承完整 ALab process environment。
- `env_mode = "none"` 不继承 host environment variables。
- Effective env 是 inherited env，然后 `[env]`，然后 `[secret_env]`，然后 ALab internal variables。
- `env_mode = "full"` 会 render stable warning，因为 `[secret_env]` 以外的 host environment variables 不保证从 runner output 中 redacted。
- Local runner stdin 是 `DEVNULL`。
- Local runner 在独立 process group 中启动 subprocess。
- Timeout 时 ALab terminate process group，短暂等待后必要时 force-kill process group。
- Timeout status 仍进行 best-effort log/artifact capture。

## 5. Docker Runner

范围：

- 只支持一个 image source：`runner.image` 或 `runner.dockerfile` plus `runner.context`。
- V1 不支持 Docker Compose。
- V1 不支持 custom cache backend。
- Docker config 使用显式 allowlist。Raw Docker CLI argument passthrough 被拒绝。
- Whitelisted build/run fields 是 `runner.build_args`、`runner.target`、`runner.platform`、`runner.user`、`runner.cpus`、`runner.memory_mb`、`runner.network`、`runner.image`、`runner.dockerfile`、`runner.context`。
- `runner.build_args` 是 string key 到 string value 的 map。Build args 是普通 config value，不是 secret value，并会出现在 config export 中。
- `runner.target` 选择 Dockerfile build target。
- `runner.platform` 在本地 Docker 支持时传递 Docker platform selector。
- V1 会在 config write 前验证 configured Docker platform selector。`linux` 使用粗粒度 Linux container capability。`linux/amd64` 和 `linux/arm64` 使用从 Docker native runtime architecture 与 reported Buildx platforms 推导出的 per-architecture capability rows。
- 不支持或未知的 platform selector 会在写入 project config 前以 `CONFIG_INVALID` 使 config validation 失败。
- `runner.user` 为 main runner process 传递 container user。ALab capture 时不提升权限。
- `runner.cpus` 和 `runner.memory_mb` 在 Docker 支持时传递 CPU 和 memory limit。
- 如果 configured Docker CPU 或 memory limit 不被本地 Docker environment 支持，config validation 在写入前以 `CONFIG_INVALID` 失败。
- 如果 `runner.image` 本地不存在，ALab 在 container execution 前运行 `docker pull` 拉取该 image。Pull failure 在存在 result record 时记录 saved validation/run status `error` 和 `RUNNER_ERROR`。
- Automatic image pull 是 V1 对 `runner.image` 的唯一 pull policy；V1 没有 `pull_policy` config field。
- V1 不支持额外 user-configured host mount、bind mount、named volume、device 或 privileged mode。

Path rules：

- `runner.dockerfile` 和 `runner.context` 是 repo-relative paths，在 temporary workspace 内 resolve。
- Normalize 后不得 escape repository。
- Dockerfile builds 遵循 configured build context 的 Docker `.dockerignore` semantics。Dockerfile image cache key 只来自 build inputs：Dockerfile content、存在时的 `.dockerignore` content、effective filtered build context content、`runner.build_args`、`runner.target` 和 `runner.platform`。
- Docker run-time fields，例如 `runner.command`、`runner.shell`、`runner.user`、`runner.network`、`runner.cpus`、`runner.memory_mb`、timeout、environment、artifact/log/reward settings，会存入 config/run records，但不改变 image cache key。
- ALab 使用由 project id 和 cache key 派生的 ALab-owned tag 标记 cached Dockerfile images，并在 SQLite 中记录 safe cache metadata。
- `alab cache prune --docker-images` 和 top-level `alab cache prune --all` 删除 ALab-owned image cache entries。

Container contract：

- Temporary workspace read-write mount 到 `/app`。
- Temporary run directory read-write mount 到 `/logs/alab`。
- `runner.working_directory` 映射到 `/app/<runner.working_directory>`。
- `ALAB_WORKSPACE=/app`。
- `ALAB_RUN_DIR=/logs/alab`。
- `runner.command` 在 container 中按 argv 执行。`runner.shell` 在 container 中按 `/bin/sh -c <shell>` 执行；若 `/bin/sh` 不存在，则以 `RUNNER_ERROR` 失败。

Network：

- `runner.network = "default"` 使用 Docker default networking。
- `runner.network = "none"` 使用 Docker no-network mode。
- `runner.network = "host"` 在 V1 不支持，并以 `CONFIG_INVALID` 失败。
- Runtime capability probes 仍用于 Docker availability、粗粒度 Linux platform support、per-architecture Linux platform support 和 CPU/memory limit support。Probe results 按 runtime fingerprint 缓存；fingerprint 改变时，ALab 重新 probe。
- `alab config validate --refresh-capabilities` 清除 cached capability results 并重新运行 probes。
- 不支持 configured CPU 或 memory limit 时，在 config write 前以 `CONFIG_INVALID` 失败。

Capture：

- Capture 前 ALab 做 best-effort host-side readability checks。
- Host 因 container ownership/permissions 无法读取的 files 记录为 artifact capture errors 或 skipped entries。
- ALab 不使用 elevated privileges 重试 capture。
- 如果 `runner.user` 导致 workspace 或 run output 对 host 不可读，run status 仍由 runner exit 和 reward parsing 决定；不可读文件记录为 capture warning 或 artifact error。
- Docker image setup/build stdout 或 stderr 会按 configured secret bytes redaction 后存为 hidden log output，且不合并到 user-visible runner stdout/stderr。捕获到 setup output 时，保存的 run/validation 会渲染 `DOCKER_SETUP_OUTPUT_CAPTURED`。

## 6. Reward Types

Reward types：

- `exit_code`：exit code `0` 映射 `1.0`；non-zero 映射 `0.0`。
- `file`：从 configured `workspace:` 或 `run:` path 读取 reward。
- `stdout_regex`：从 stdout capture 提取 reward。
- `harbor`：读取 Harbor verifier reward output。
- `skydiscover`：从 evaluator metrics 读取 primary metric。

通用规则：

- ALab 对每个 run 都尝试 reward extraction，包括 non-zero exit。
- Runner exit code 决定 pass/fail。
- Exit code `0` 但 reward parse failure 使 status 为 `error`。
- Non-zero exit 且 reward parse failure 保持 `failed`，并记录 parse failure。
- Ranking 需要 parsed finite numeric reward。
- `NaN`、`Infinity`、missing value、empty string、non-numeric value 都导致 parse failure。

File reward：

- `reward.path` 必须 rooted at `workspace:` 或 `run:`。
- Path resolution 使用 artifact root escape checks。
- Reward file read limit 复用 `artifacts.per_file_limit_bytes`。
- Plain text 按 stripped finite float 解析。
- JSON reward file 必须是 top-level string-to-finite-number object。
- JSON reward metrics 只支持 top-level keys；V1 不支持 nested path。
- ALab 读取 top-level object 中的 `reward.primary_metric`。

Stdout regex reward：

- 必须配置 `reward.pattern`。
- Extraction 读取 ALab 存储的 redacted、truncated stdout。
- 如果 regex 有 named group `reward`，解析该 group；否则解析第一个 capture group。
- 如果 reward text 在 stdout truncation 后丢失，parse 可失败并记录 `REWARD_PARSE_ERROR`。

Harbor reward：

- 读取 `run:/logs/verifier/reward.txt` 或 `run:/logs/verifier/reward.json`。
- `reward.json` 必须是 top-level string-to-finite-number object。
- 默认读取 `reward.primary_metric = reward`。
- Missing、non-finite 或 non-numeric metric value 都会使 reward parsing 失败。详细 verifier diagnostics 必须写入单独 logs 或 artifacts，不能写入 reward metrics object。

SkyDiscover reward：

- 默认 `reward.primary_metric` 是 `combined_score`。
- 显式配置 primary metric 时，缺失该 metric 使 parsing 失败。
- 使用默认 primary metric 且缺失 `combined_score` 时，ALab 对所有 finite numeric top-level metrics 求平均。
- 没有 finite numeric top-level metrics 时 parsing 失败。

## 7. Artifact Capture

Artifact roots：

- `workspace:` 表示 temporary clean checkout root。
- `run:` 表示 temporary run output directory。
- 无 prefix artifact glob 表示 `workspace:`。
- `hidden:` 不是 valid artifact root。

规则：

- Artifact path 经 symlink/path normalization 后不得 escape root。
- Artifact root containment checks 使用 normalized path ancestry，而不是 string-prefix matching。
- Artifact glob matching 使用相对于所选 artifact root 的 Python `glob` semantics，包括 `**` recursive matching。ALab 将 separator normalize 为 `/`，按 resolved path 去重，并按 normalized relative path 稳定排序后 capture。
- Glob 匹配 symlink 时，ALab resolve 它。
- Resolved target 留在 artifact root 内时 capture target bytes。
- Escape root 的 symlink 被 skipped，并记录 status `skipped`。
- Directory matches 递归 capture，受 per-file/per-run limits 限制。
- Directory matches 展开为每个 captured file 一条 artifact record。
- V1 不创建 directory artifact 或 automatic zip archive。
- Stdout/stderr 是 logs，不是 artifacts。
- Oversized artifacts 被 skipped，且不改变 run/validation status。
- Capture errors 不改变 run 或 validation status。
- Capture errors 记录为 artifact statuses 和 `ARTIFACT_CAPTURE_ERROR` warnings。
- 只要存在 run 或 validation record 且 temporary runtime directories 仍可用，ALab 会对 passed、failed、error 和 timeout results 尝试 artifact capture。Runner exit failure、reward parse failure 和 timeout 本身不会禁用 artifact capture。
- Artifact export 写 exact captured bytes。
- V1 不 redact artifact contents。
- Active `secret_env` values 与 artifact globs 同时配置时，run/validation output 必须 warn：artifact bytes 是 exact bytes，不会自动 redacted。
- Artifact archive、unarchive、remove 和 archived show/export 规则定义在 [spec_lifecycle.md](spec_lifecycle.md)。

Blob storage：

```text
~/.ALab/projects/<project_id>/artifacts/blobs/sha256/<first-two-hex>/<sha256>
```

- `artifacts.blob_path` 存 project artifact store 的 relative path。
- 相同 content hash 可被多个 artifact records 引用。
- Artifact blob file 只有在没有任何剩余 artifact row 引用时才删除。

## 8. Logs

规则：

- Stdout 和 stderr byte limits 相互独立。
- Secret redaction 在 truncation 和 storage 前发生。ALab 先对 captured stream 中每个 active secret value 执行 exact UTF-8 byte replacement，再对 redacted stream 应用 configured stored byte limit。
- 超过 limit 的 logs 被 truncated，并标记 `truncated = true`。
- Logs 是 byte files plus SQLite metadata，不是 authoritative SQLite text。
- `preview_text` 是 CLI rendering 用的 safe UTF-8 replacement-decoded prefix。
- `runs show` 输出 fixed-size stdout/stderr previews 和 log metadata。
- Full visible logs 通过 `observe logs show|export` 访问；`show` 会将 stored log bytes 以 safe UTF-8 replacement-decoded `content` 渲染。
- Hidden logs 需要 root/admin 且显式 `--include-hidden`。
- Log archive、unarchive、remove 和 archived show/export 规则定义在 [spec_lifecycle.md](spec_lifecycle.md)。
- Shared log files 只有在没有任何剩余 log row 引用时才删除。

Visible streams：`stdout`、`stderr`。

Hidden streams：`hidden_stdout`、`hidden_stderr`。

Hidden log rules：

- Harbor 和 SkyDiscover raw verifier/evaluator stdout/stderr 存为 admin-only hidden logs。
- Token-visible output 只显示 safe summaries、metric names、reward values、sanitized feedback。
- Hidden logs 绝不通过 token-scoped commands export。

## 9. Hidden Validation Assets

Hidden validation assets 包括 private verifier scripts、private tests、private test data、evaluator bundles，以及不应暴露给 agent 的 adapter metadata。

规则：

- Hidden validation assets 绝不能 import 到 source refs。
- 绝不能复制到 experiment worktrees。
- 绝不能复制到 inspection worktrees。
- 绝不能作为 artifacts export。
- Validation/run execution 中只能 materialize 在 temporary `workspace` 和 `run_dir` 外，例如 `hidden_dir`、adapter staging、或不挂载到 editable workspace 的 container path。
- Token-scoped CLI output 不得渲染 hidden asset contents、absolute host paths、staging paths、full verifier commands、private test names、private test data。
- Admin/root output 可显示 safe summaries、stable hashes、catalog refs、runner type、evaluator type、高层 task identifiers，但不显示 hidden asset contents。
- 这些规则防止 CLI/worktree disclosure，不是 OS-level secrecy guarantee。

## 10. Harbor Adapter

范围：

- V1 支持 single-step Harbor tasks。
- V1 支持 shared verifier 和 separate verifier。
- V1 不支持 Windows tasks。
- V1 不支持 multi-step tasks。

Supported task files：

- `instruction.md`
- `task.toml`
- `environment/`
- `tests/test.sh`
- 用于 separate verifier image build 的 `tests/Dockerfile`

Editable source：

- 如果 Harbor task 声明 supported `source` file 或 directory，ALab 只 import 该 source 作为 editable source。
- Harbor `source` value 只有在它是 task-relative path、path normalization 后仍在 task directory 内、且不指向 `tests/`、`environment/`、`solution/`、verifier assets 或 task-private files 时才 supported。
- 如果没有 supported source 且未提供 explicit ALab source selector，ALab 创建 empty source。
- Empty-source fallback 是 Harbor V1 的 supported behavior，不是 error。生成的 project 仍必须通过 baseline validation 后才能创建新 experiments。
- ALab 绝不把 `tests/`、`environment/`、`solution/`、verifier assets 或 task-private files import 为 editable source。

Environment：

- Supported environment inputs 是 Docker image 或 `environment/Dockerfile`。
- Missing OS 视为 Linux。
- `environment.allow_internet = false` 在用户未显式配置 `runner.network` 时映射为 `none`。
- `environment.allow_internet = true` 或 omitted 在用户未显式配置 `runner.network` 时映射为 `default`。
- `environment.cpus` 映射到 Docker `--cpus`。
- `environment.memory_mb` 映射到 Docker `--memory`。
- CPU/memory resource support 在 config write 前检查。

Verifier：

- Shared verifier 使用 task environment 和 `tests/test.sh`。
- Separate verifier 支持 verifier image 或 `tests/Dockerfile`。
- Verifier workspace mount 是 temporary 且 writable。
- Verifier assets 是 hidden validation assets。
- Raw verifier stdout/stderr 是 hidden logs，仅 admin 可见。
- Token-visible records 只能显示 verifier status、reward、metric names、safe summaries。

Task text：

- `instruction.md` 可成为 visible project task text。
- 如果用户通过 CLI/config 提供 explicit ALab task text，则 explicit task text 优先，`instruction.md` 只保留在 origin metadata。

Unsupported fields：

- Multi-step tasks。
- Windows 或 non-Linux OS。
- GPU requirements 和 `gpu_types`。
- `storage_mb`。
- MCP servers。
- Healthchecks。
- Custom resource scheduling。
- External services。
- Docker Compose 或等价 multi-container runtime。
- `task.toml` 中的 host environment placeholders。
- Raw Docker argument passthrough 和 task-declared extra host mounts。

规则：

- Unsupported runtime-affecting fields 以 `CONFIG_INVALID` 失败。
- Metadata/descriptive fields 可在记录 safe origin metadata 后忽略。
- `${TOKEN}` 等 placeholder values validation fail。
- 所有 literal Harbor task environment values 都注入为 secret environment values，并按 `secret_env` redact，不依赖 Harbor task schema 是否标注为 secret。
- `solution/` excluded，绝不能成为 editable source。

## 11. SkyDiscover Adapter

Catalog commands：

```text
alab catalog skydiscover add [--origin-url <url>] [--ref <ref>|--commit <sha>]
alab catalog skydiscover update [--origin-url <url>] [--ref <ref>|--commit <sha>]
alab catalog skydiscover show
alab catalog skydiscover remove --force --confirm skydiscover [--reason <text>]
```

规则：

- Catalog commands 需要 root key。
- `add` 在 catalog 缺失时 clone SkyDiscover 到 `~/.ALab/sources/skydiscover/`。
- `update` refresh existing catalog 到新的 pinned upstream commit。
- `--origin-url` 默认 official SkyDiscover repository URL。
- 当既未提供 `--ref` 也未提供 `--commit` 时，ALab resolve 当前 upstream `main` 并 pin exact commit。
- `--ref` resolve branch、tag 或 commit-ish，并存 resolved exact commit。
- `--commit` 要求 full commit SHA，并在 selected origin 中验证存在后存 exact commit。
- `show` 输出 pinned commit、origin URL、retrieval time、local path，且不 fetch network。
- Catalog pin exact upstream commit。
- ALab 不自动 follow upstream `main`。
- Resolving missing `skydiscover:<path>` 绝不 auto-update catalog。
- 如果不存在 active SkyDiscover catalog，任何解析 `skydiscover:<path>` 的命令都以 `CONFIG_INVALID` 失败，并给出 next action：运行 `alab catalog skydiscover add`。Active catalog 中缺失的 paths 也以 `CONFIG_INVALID` 失败；ALab 在解析 task 或 evaluator 时绝不 auto-fetch 或 auto-update catalog。
- `update` 遇到 local catalog 有 non-ALab modifications、untracked files、unexpected remote URL 时失败。
- `remove` 只有在没有 active project config 且没有 open experiment bound config 引用 SkyDiscover catalog task 或 evaluator bundle 时，才删除 local catalog 并将 catalog metadata 标记 removed。
- Catalog removal 后 closed 和 archived experiment history 仍可 observe，因为 run records、metrics、safe feedback、logs、artifacts 和 annotations 不依赖 live catalog files。
- Docker image、SkyDiscover evaluator environment 和 ALab trash entries 的 cache cleanup 由 [spec_lifecycle.md](spec_lifecycle.md) 定义的 `alab cache prune` 处理。

Catalog references：

```text
skydiscover:<path-inside-benchmarks>
```

- Catalog references 标识 evaluator bundle 或 Harbor-compatible task。
- 它们本身不标识 editable source code。
- Missing path 或 unrecognized evaluator/task format 使 config validation 失败。

Source precedence：

- 对 `project init skydiscover`，显式 editable source 仅限 `--source-path`、`--source-git` 或 `--source-empty`。
- `project init skydiscover` 拒绝 `--source-ref`；existing ALab source 是 project-scoped reproducibility record，不是 cross-project init input。
- 如果没有 explicit editable source 且 benchmark 有 initial program file/directory，ALab 只导入该 initial file/directory 作为 editable source。
- 如果没有 initial program，init 失败并要求 explicit source。
- SkyDiscover benchmark directory 不会整体作为 editable source 导入。

Evaluator-only：

- SkyDiscover 在 ALab V1 中只作为 evaluator。
- ALab 不调用 SkyDiscover search loops、proposal generation、mutation、autonomous optimization commands 或 scheduling loops。

### SkyDiscover Docker Evaluator

规则：

- Materialize evaluator Dockerfile 和 `evaluate.sh` 到 local task bundle。
- Evaluator Dockerfile、`evaluate.sh`、support files、benchmark-private data 都是 hidden validation assets。
- 在 Docker 中对 temporary workspace build/run evaluator。
- Editable temporary workspace 与 evaluator assets 分开 mount。
- 不得把 evaluator assets copy 回 workspace。
- 从 stdout JSON 解析 top-level metrics。
- Evaluator `artifacts` JSON 存入 run feedback，除非被 artifact globs 捕获，否则不转换为 file artifacts。
- Token-visible output 可显示 task ref、pinned catalog commit、evaluator mode、metric names、reward value、sanitized feedback。
- Token-visible output 不得显示 evaluator source contents、hidden test data、absolute catalog paths、staging paths。

### SkyDiscover Python Evaluator

规则：

- SkyDiscover Python evaluator support 是 full V1 adapter capability，不是 experimental 或 V2-only feature。
- Materialize evaluator Python files 到 local task bundle。
- Evaluator files 和 benchmark-private data 是 hidden validation assets。
- 通过 ALab wrapper subprocess 执行 evaluator code。
- Main ALab process 不得 import evaluator code。
- Python evaluator 不是 OS sandbox。当配置 SkyDiscover Python runner 时，root/admin output 和 config summaries 必须明确说明这一点。
- 调用 `evaluate(program_path)`，`program_path` 默认 temporary workspace root。
- Python evaluator dependencies 安装到 ALab-managed `uv` environment，位于 project/experiment worktrees 外。
- 有 `pyproject.toml` 或 `uv.lock` 时，用 `uv sync` create/reuse environment。
- 有 `requirements.txt` 且无 `pyproject.toml` 时，用 `uv pip install -r requirements.txt`。
- Environment cache key 来自 evaluator dependency file hashes、host platform，以及 evaluator environment 使用的 Python version。
- Dependency installation 可使用 default network。
- Installation failure 记录 `RUNNER_ERROR` 并使 baseline/run fail。
- 解析 returned JSON-serializable metrics 和 feedback。

## 12. Docker Unavailable

规则：

- Docker unavailable 时 Docker/Harbor/SkyDiscover Docker validation record status 为 `error`。
- Project 变 invalid。
- Optional Docker-dependent tests 在 Docker unavailable 时 skip。

## 13. References

Planning references checked on 2026-05-16：

- Harbor task documentation: https://www.harborframework.com/docs/tasks
- Harbor multi-step task documentation: https://www.harborframework.com/docs/tasks/multi-step
- Harbor Windows task documentation: https://www.harborframework.com/docs/tasks/windows-container-support
- SkyDiscover README and evaluator formats: https://github.com/skydiscover-ai/skydiscover
- Docker none network driver documentation: https://docs.docker.com/engine/network/drivers/none/
