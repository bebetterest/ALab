# ALab V1 Project、Source、Experiment、Run 和 Submit 规格

本文档是 [spec_project_source_experiment.md](spec_project_source_experiment.md) 的中文同步版。英文版是规范性来源。跨对象 archive、unarchive、remove、restore 和 audit 语义定义在 [spec_lifecycle.md](spec_lifecycle.md)。

## 1. Project Config Schema

Project definition 以 TOML import/export，并以 canonical JSON 存储。

Minimal TOML：

```toml
schema_version = 1

[project]
name = "Example Project"
goal = "Optional high-level goal"
task = "Task text"
allow_public_exp_create = true

[source]
default_source_ref = "alab/source/src-base-abc123"

[public_source_import]
enabled = true
max_files = 100000
max_total_bytes = 1073741824
max_file_bytes = 104857600

[mutable]
include = ["**"]
exclude = []

[visibility]
scope = "same_project"
experiment_ids = []

[runner]
type = "local"
timeout_seconds = 600
working_directory = "."
env_mode = "sanitized"
command = ["uv", "run", "pytest"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = []
per_file_limit_bytes = 10485760
per_run_limit_bytes = 104857600

[logs]
stdout_limit_bytes = 10485760
stderr_limit_bytes = 10485760

[git]
author_name = "ALab"
author_email = "alab@local"

[env]
PYTHONUNBUFFERED = "1"

[secret_env]
# TOKEN = "..."
```

字段规则：

- `schema_version` 必须是 `1`。
- `project.name` 和 `project.task` 是 required non-empty strings。
- `project.goal` 可选。
- `project.allow_public_exp_create` 默认 `true`。
- Project、source、experiment display name UTF-8 编码后最长 120 bytes。
- Name uniqueness 按 normalized slug 判定，不按 exact string。
- Task、goal、summary、feedback、annotation body 各自 UTF-8 编码后最多 65536 bytes。Annotation title UTF-8 编码后最多 256 bytes。
- 一个 project 可以包含多个 source records。Stored canonical project config 包含一个 `source.default_source_ref`，且它在创建新 experiment 前必须 resolve 到 active source。
- 每个 experiment 创建时只绑定一个 source。如果 `exp create` 没有选择 source 或 `--from-exp`，ALab 使用 active config 的 `source.default_source_ref`。
- 当 init 命令提供一个 effective default source origin 时，project init 的输入 config 可以省略 `source.default_source_ref`。ALab 先 staging 该 source，把 canonical `alab/source/<source_id>` ref 注入 stored config，然后验证完整 canonical config。
- 如果 project init 输入 config 包含 `source.default_source_ref`，该值是 expected canonical source ref。若它与 staged canonical source ref 不同，init 以 `CONFIG_INVALID` 失败；ALab 不得静默 overwrite。
- `project.allow_public_exp_create` 和 `public_source_import.enabled` 是 strict booleans。
- `public_source_import.enabled` 默认 `true`。
- Public source import limits 默认等于 normal source limits，并可由 project config 配置；V1 没有额外 hard-coded cap。
- `public_source_import.max_files`、`public_source_import.max_total_bytes` 和 `public_source_import.max_file_bytes` 必须是 non-negative integers。
- Public caller 不能在命令行把 public import limits 上调。
- `mutable.include` 默认 `["**"]`，且必须至少包含一个 non-empty single-line pattern；`mutable.exclude` 默认 `[]`，设置时包含 non-empty single-line patterns。
- `visibility.scope` 是 `none`、`same_project` 或 `explicit`。
- 只有 `scope = "explicit"` 时，`visibility.experiment_ids` required 且 non-empty；entries 必须是 complete experiment ids，并会 normalized 为 sorted unique list。
- `runner.type` 是 `local`、`docker`、`harbor`、`skydiscover_docker` 或 `skydiscover_python`。
- `runner.timeout_seconds` 默认 `600`，必须是 `1` 到 `86400` 之间的 integer。
- `runner.working_directory` 是 repo-relative，不能 escape repository。
- `runner.env_mode` 仅 local runner 有效，取值 `sanitized`、`full`、`none`。
- Docker-backed runner 的 `runner.network` 是 `default` 或 `none`，默认 `default`。
- Docker host networking 在 V1 不支持。`runner.network = "host"` 以 `CONFIG_INVALID` 失败。
- `runner.command` 在提供时必须是 non-empty argv list mode；`runner.shell` 在提供时必须是 non-empty explicit shell mode；二者冲突。`runner.shell` 在 V1 只对 local runner 和 Docker runner shell mode 有效。Harbor 和 SkyDiscover adapters 拥有自己的 verifier/evaluator commands，并拒绝用户提供的 `runner.shell`。
- Docker runner 需要且只需要 `runner.image` 或 `runner.dockerfile` 之一。
- Dockerfile runner 需要 `runner.context`。
- Docker runner 可设置 whitelisted Docker fields：`runner.build_args`、`runner.target`、`runner.platform`、`runner.user`、`runner.cpus`、`runner.memory_mb`。
- Docker runner 拒绝 raw Docker CLI argument passthrough 和 extra host mount/volume。
- `runner.cpus` 和 `runner.memory_mb` 对 Docker-backed runner 有效，前提是本地 Docker environment 支持。`runner.cpus` 必须是 positive finite number，`runner.memory_mb` 必须是 positive integer。如果配置的限制不被支持，config validation 在写入前以 `CONFIG_INVALID` 失败。
- Harbor runner 需要 `runner.harbor_task_ref`。
- SkyDiscover runner 需要 `runner.skydiscover_task_ref`。
- SkyDiscover Python runner 可设置 `runner.program_path`，默认 `"."`。
- `reward.type` 是 `exit_code`、`file`、`stdout_regex`、`harbor`、`skydiscover`。
- `reward.direction` 是 `maximize` 或 `minimize`。
- `reward.primary_metric` 默认 `reward`，SkyDiscover 默认 `combined_score`。
- `reward.type = "exit_code"` 要求 `reward.direction = "maximize"`。
- `artifacts.globs = []` 表示无额外 artifact。
- `artifacts.per_file_limit_bytes`、`artifacts.per_run_limit_bytes`、`logs.stdout_limit_bytes` 和 `logs.stderr_limit_bytes` 必须是 positive integers。
- `logs.*_limit_bytes` 默认 `10485760`。
- `env` 是 valid environment variable name 到 string 的 map。`secret_env` input values 是至少 4 个 UTF-8 bytes 的 single-line strings，或 config-import retain markers。Names 必须匹配 `^[A-Za-z_][A-Za-z0-9_]*$`。

Baseline trigger：

- Runtime-affecting fields 触发 baseline：`source.default_source_ref`、所有 `runner.*`、所有 `reward.*`、`artifacts.*`、`logs.*`、`env.*`、`secret_env.*` 和 timeout fields。
- Policy/metadata fields 本身不触发 baseline：`project.goal`、`project.task`、`project.allow_public_exp_create`、`public_source_import.*`、`mutable.*`、`visibility.*`、tags、Git author metadata。

Config edit：

- `project config import`、`project config set`、`project env`、`project secret` 都基于 `latest_attempted_config_version`。
- `project config set` 接受任意非 secret 字段的 TOML literal，包括 arrays 和 maps。`[secret_env]` changes 必须使用 `project secret` 或 config import retain markers。
- `project config set` 对 map 或 array 字段执行完整字段替换；V1 不做 deep merge。
- 如果 config edit 的 `config_hash` 与 current latest attempted version 完全相同，该命令是 no-op，不创建新 version。
- 回滚到旧 config content 会创建新的 monotonic config version，除非它与 current latest attempted version 完全相同。
- Invalid runtime config 不能通过 metadata-only changes 变 valid。
- `project validate` 验证 latest attempted config。
- `project config import --dry-run` 和 `project config set --dry-run` 解析并 canonicalize input，计算 effective diff，判断是否需要 baseline，并运行 Docker availability/resource support 等 runtime capability check。它们不写 SQLite rows，不修改文件，不执行 baseline runner，也不创建 audit event。

Config read/export 规则：

- `project config show` 和 `project config export` 默认使用 `--version latest-attempted`。
- `--version latest-attempted` 选择 `projects.latest_attempted_config_version`。
- `--version active-valid` 选择 `projects.active_valid_config_version`，没有 active valid config 时以 `PROJECT_INVALID` 失败。
- `--version <n>` 选择显式正整数 retained config version number。
- Exported TOML 始终对 `[secret_env]` 使用 secret retain marker，不论选择哪个 version。

## 2. Project Lifecycle

Project statuses：

- `valid`：`active_valid_config_version` 对 default source 和 runner config 有 passed baseline validation。
- `invalid`：latest attempted runtime-affecting config version baseline failed/errored/timed out/skipped。
- `archived`：project 保留，但禁止 new experiment 和 run/submit。

Archive/unarchive：

- `project archive` 需要 root/admin。
- Active validation、source import、run、submit、worktree maintenance 或其他 project maintenance lock 存在时，project archive 以 `RESOURCE_BUSY` 失败。
- Archive 是纯状态变更；不删除 Git refs、worktrees、sources、experiments、runs、artifacts、logs、credentials 或 annotations。
- Archive 存储 `pre_archive_status`。
- `project unarchive` 恢复 `pre_archive_status`。
- 如果 project archived 前是 invalid，unarchive 后仍是 invalid；如果 archived 前是 valid，unarchive 后是 valid。
- `project remove` 仅 root 可执行，并遵循 [spec_lifecycle.md](spec_lifecycle.md) 中的 archive-first、`--cascade` 和 audit 规则。

Validation：

- Project creation 和 runtime-affecting config change 默认运行 baseline。
- `--skip-baseline-test` 写入 valid schema change、存 skipped validation record、保持 `active_valid_config_version` 不变，把 project 标记 invalid，并以 exit `0` 结束。
- Skipped baseline validation 绝不视为 project runnable 的证明。New experiment 仍被阻止，直到 `project validate` 通过。
- Baseline validation 在 runner execution 前创建 `running` validation record，capture 后更新 final status。
- 后续 project maintenance/config/validation/status operation 会把 stale `running` validation records 标为 `interrupted`。
- Baseline failure 将 project 标记 invalid，并存 logs、artifacts、已解析 reward 和 failure reason。
- Existing experiments 继续使用创建时绑定的 config version，包括 `env` 和 `secret_env`。
- Project 变 invalid 后，已有 open experiments 可继续使用其 bound valid config version。
- New experiments 要求 project valid。

## 3. Project Init

Commands：

```text
alab project init local --config <path> --source-path <path> ...
alab project init git --config <path> --source-git <url> [--git-ref <ref>] [--source-subdir <path>] ...
alab project init empty --config <path> --source-empty ...
alab project init harbor --config <path> --harbor-task <path|skydiscover:path> [--source-path <path>|--source-git <url>|--source-empty] ...
alab project init skydiscover --config <path> --skydiscover-task <path|skydiscover:path> [--source-path <path>|--source-git <url>|--source-empty] ...
```

通用规则：

- 需要 root key。
- `auth init` 必须已运行。
- Project init 在写入 project record 时始终创建一个 project admin key。
- Raw admin key 只显示一次，SQLite 只存 verifier。
- 即使随后 baseline validation failed 并保留 invalid project，admin key 也已经创建并只显示一次。
- 如果 project init baseline validation 失败，ALab 保留 project、source、config version、validation record、logs、artifacts、failure reason；project status 变 `invalid`。

Input precedence：

1. Load required `--config`。
2. Apply mode-specific source/Harbor/SkyDiscover data。
3. Apply allowed CLI metadata overrides：project `--name`、`--task`、`--goal` 和 source selectors。
4. Validate source-independent schema fields。此阶段只有 init 命令提供一个 effective default source origin 时才允许缺少 `source.default_source_ref`。
5. Stage project repository，并 import/create effective default source；如提供 init-time source import limits，必须在写入 project rows 前完成校验。
6. 如果 adapter-derived editable source 和 explicit caller source 同时存在，比较 canonical tree hash。内容相同正常 dedupe；内容不同以 `SOURCE_INVALID` 和稳定 source conflict reason 失败。
7. 当 input config 省略 `source.default_source_ref` 时，注入 staged canonical source ref。若 input config 提供了不同 ref，以 `CONFIG_INVALID` 失败。
8. Validate full canonical config。
9. Filesystem staging 成功后，在一个短 SQLite transaction 中写入 project、source、config、path registry 和 initial admin credential verifier rows。
10. Render raw admin key exactly once。
11. Run baseline unless skipped。

Runtime config：

- Baseline validation 前 project 必须有完整 runner 和 reward policy。
- V1 每种 project init mode 都要求 `--config`。
- Runner、reward、artifact、log、env、secret、Docker、Harbor 和 SkyDiscover runtime fields 都从 project config 读取，而不是 init flags。
- ALab 不得 silently default reward type。Config 必须提供完整 reward policy。
- Init source flags 是唯一 init-time runtime-affecting overrides，只用于 project creation 时 bootstrap initial default source；不得静默替换 input config 中冲突的 `source.default_source_ref`。
- Project init 接受与 source import 相同的 source limit options（`--max-files`、`--max-total-bytes`、`--max-file-bytes`）来限制 staged initial source。取值必须是 non-negative integers。Malformed 或 negative limit values 以 `CONFIG_INVALID` 失败；exceeded limits 会在 source staging 或写入 project/source/config/admin credential rows 前以 `SOURCE_LIMIT_EXCEEDED` 失败。
- Remote Git source 用 `--git-ref <branch|tag|sha>`。
- `--source-ref` 始终表示 existing ALab source id 或 `alab/source/<source_id>`，不得用作 remote Git ref。
- `project init harbor` 和 `project init skydiscover` 在 V1 不接受 `--source-ref`。新的 adapter project 必须从 `--source-path`、`--source-git`、`--source-empty` 或 adapter-derived editable source bootstrap initial editable source。Existing ALab source 是 project-scoped reproducibility record，不是 cross-project init input。

## 4. Source Model

外部代码通过不可变 source refs 进入 ALab：

```text
alab/source/<source_id>
```

Git storage：

- CLI name 映射到 canonical repository 中的 `refs/heads/alab/source/<source_id>`。
- Source import 创建一个 filtered snapshot commit。
- V1 Git import 不保留 upstream history。
- Snapshot fidelity 遵循 Git semantics：file contents、paths、executable bit、symlink；不保留 mtime、owner、group、extended attributes。
- Source `tree_hash` 使用 `alab-tree-sha256-v1`：ALab 从 filtered tree 构建按 repo-relative path 排序的 canonical manifest。每个 manifest entry 记录 path bytes、Git file mode、entry kind、symlink 的 target bytes，以及 regular file 的 SHA-256 content hash。最终 tree hash 是 `sha256:` 加 canonical manifest 的 SHA-256 digest。它不依赖 Git object hash format。
- V1 不支持 Git submodules/gitlinks 作为 source entries。如果 filtering 后仍存在任何 gitlink entry，import 以 `SOURCE_INVALID` 失败，并给出 next action：先 vendor 或展开 submodule contents 再 import。

Commands：

```text
alab source import --project <project_id> --source-path <path> [--source-subdir <path>] [--name <name>] [--max-files <n>] [--max-total-bytes <n>] [--max-file-bytes <n>]
alab source import --project <project_id> --source-git <url> [--git-ref <ref>] [--source-subdir <path>] [--name <name>] [--max-files <n>] [--max-total-bytes <n>] [--max-file-bytes <n>]
alab source import --project <project_id> --source-empty [--name <name>]
alab source list [--project <project_id>] [--include-archived]
alab source show <source_id> [--project <project_id>]
alab source archive <source_id> [--project <project_id>]
alab source unarchive <source_id> [--project <project_id>]
alab source remove <source_id> [--project <project_id>] (--dry-run|--force --confirm <source_id>) [--cascade] [--reason <text>]
```

Authorization：

- Standalone source commands 需要 root/admin。
- Public `exp create --source-*` 可在 public experiment creation 和 public source import policy 允许时 inline import source。

Source selection：

- 每次 source origin 选择只能使用 `--source-ref`、`--source-path`、`--source-git`、`--source-empty` 中一个。
- `--source-subdir` 可用于 local path 和 remote Git import。
- Existing source 可用 `src-...` 或 `alab/source/src-...`。
- CLI output 使用 canonical `alab/source/<source_id>`。
- Remote Git import 用 `--git-ref <branch|tag|sha>` 选择 upstream ref；省略时 resolve remote HEAD。
- `skydiscover:<path>` 是 task/evaluator catalog URI，不是 V1 editable source kind。

Source names：

- Source name 可省略。
- 省略时 ALab 自动派生：local path basename、Git URL repo basename plus selected ref、`empty`、Harbor task basename、SkyDiscover benchmark basename。
- 派生名仍需在 project 内按 normalized slug 唯一。
- Public inline import 遇到派生名冲突时，可基于 source id 追加短 deterministic suffix；root/admin standalone import 遇到 supplied/derived name 冲突时以 `NAME_CONFLICT` 失败，除非用户改 `--name`。

Default limits：

- `100000` files。
- `1073741824` total bytes。
- `104857600` bytes per file。

Limit rules：

- Root/admin imports 可调高或调低 limits。
- Public no-key inline import 使用 `[public_source_import]` limits。
- Public limits 可配置，且没有额外 hard-coded cap。
- Public caller 可在命令中调低 limits，但不能超过 configured public limits。Policy-ceiling failures 必须在 source path reads、source copies、Git clones、source records 或 experiment rows 之前被发现。
- 超限以 `SOURCE_LIMIT_EXCEEDED` 失败，不创建 source record 或 Git source ref。
- Public no-key remote Git import 可以使用本机已有的 non-interactive Git credential helpers。helper 可用或被使用时必须渲染 `PUBLIC_GIT_CREDENTIAL_HELPER_USED`，并且 Git prompts 仍保持禁用。

Local path import：

- 捕获当前 filesystem contents，不只 Git HEAD。
- 如果 source path 在 Git worktree 内，ALab 使用 Git-native ignore evaluation，导入 tracked files 加 untracked non-ignored files。
- Tracked files 即使匹配 built-in sensitive exclude 也导入，并输出 `TRACKED_SENSITIVE_SOURCE_FILE` warning。
- Untracked files 匹配 root `.alabignore` 或 built-in sensitive excludes 时排除。
- 在 Git worktree 内，`.alabignore` 绝不排除 tracked files；tracked files 仍属于 source snapshot，并可能只渲染 warning。
- 非 Git worktree 使用 `pathspec` 应用 root `.gitignore`、optional root `.alabignore` 和 built-in sensitive excludes。
- 始终排除 `.git/` 和 `.alab/`。
- 不自动同步未来 origin changes。
- Filtering 后 empty tree 仍成功，并输出 `SOURCE_EMPTY_AFTER_FILTER`；显式 `--source-empty` 不 warning。

Built-in sensitive excludes：

```text
.git/
.alab/
.env
.env.*
*.pem
*.key
id_rsa
id_ed25519
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.DS_Store
node_modules/
dist/
build/
coverage/
```

Remote Git import：

- Clone/fetch 到 temporary directory。
- 省略 `--git-ref` 时 resolve remote HEAD。
- Git command non-interactive，禁用 prompts。
- Root/admin 和 public no-key import 都可使用 existing Git credential helpers，但会阻塞的 credential prompt 使 import 失败。
- 记录 resolved commit。
- 支持 subdir import。
- V1 不保持 live upstream tracking relationship。

Deduplication：

- ALab 在 filtering 和 subdir selection 后计算 normalized content tree hash。
- 若存在 identical active source，则返回 existing source id/ref，向 `origin_metadata_json.origins` 追加 sanitized origin entry，不创建新 source id 或 Git source ref。
- Archived sources 不参与 dedupe lookup。旧 source archived 后，相同内容可重新 import 为新的 active source。
- 如果 dedupe 时 caller 提供了不同 source name，输出 `SOURCE_DEDUPED_NAME_IGNORED`。
- Source refs immutable，永不 overwrite。

Source lifecycle：

- Active source 可创建 experiments。
- Archived source 仍可被已有 records/experiments 使用。
- Source archive 只在不是 active default source 时允许。
- 从 archived source 创建新 experiment 需要 explicit `--source-ref` plus root/admin。
- `source unarchive` 恢复 active status。
- `source remove` 要求 source 已 archived，并遵循 [spec_lifecycle.md](spec_lifecycle.md) 中的依赖和 audit 规则。
- 如果 source 被任意 project config version 引用，V1 永久禁止 hard remove，因为 config version 是 immutable reproducibility 和 audit record。

## 5. Experiment Lifecycle

Experiment statuses：

- `open`：接受 run、submit、tag、annotation。
- `closed`：final submission accepted；拒绝 run/submit；接受 observe、tag、annotation、create-from-experiment。
- `archived`：保留但默认从 list/search/best 隐藏；拒绝 run/submit；接受 show、create-from-experiment、admin maintenance。

Create command：

```text
alab exp create [--project <project_id>] --name <name> [--goal <goal>] [--path <dir>] [--tag <tag> ...] [--source-ref <ref>|--source-path <path>|--source-git <url>|--source-empty|--from-exp <exp_id>] [--git-ref <ref>] [--source-subdir <path>] [--from-commit final|latest|best|<sha>] [--mutable-include <pattern> ...] [--mutable-exclude <pattern> ...] [--visibility-scope none|same_project|explicit] [--visible-exp <exp_id> ...]
```

规则：

- Project allow public experiment creation 时，project context 或 explicit `--project` 下无需 root/admin key。
- Private project 需要 root/admin。
- Project 必须 `valid`。
- Experiment name 在 project 内按 normalized slug 唯一。所有 caller，包括 public no-key caller，遇到冲突都返回 `NAME_CONFLICT`；ALab 不自动追加 suffix。
- Public no-key 可在 custom path 通过 realpath registration、empty-directory、nesting checks 后创建。
- Custom experiment path 必须不存在或完全空目录。
- 如果省略 `--path`，ALab 在 command cwd 下创建 `./<project_id>_<exp_id>` worktree。
- Default worktree path 不得已存在。若已存在，`exp create` fail，并提示 caller 传入 `--path`。
- Default worktree 的 command cwd 可以是任意通过 realpath registration 和 nesting checks 的目录。同一 project 的 registered project control context 允许使用，并会把 default experiment worktree 创建为该 control context 的 child。不同 project 的 project control context 被拒绝。Experiment 和 inspection contexts 不允许包含 nested project、experiment 或 inspection contexts。
- Experiment origin 来自 explicit source flags、`source.default_source_ref` 或 `--from-exp`。
- 每次最多一个 origin：一个 source flag 或 `--from-exp`。
- 无 origin 时使用 `source.default_source_ref`。
- Inline source import 遵循 standalone source import 的 ignore 和 limit rules。
- `--git-ref` 只与 `--source-git` 有效。
- `--from-exp` 从 existing experiment commit 创建。
- `--from-commit` 只与 `--from-exp` 有效。
- 如果提供 `--from-exp` 但省略 `--from-commit`，ALab 默认使用 `latest`。
- Source experiment 必须对 caller 可见，或 caller 是 root/admin。
- Public project 允许 no-key `--from-exp` 从 visible `open` 或 `closed` experiment 创建。这是显式 public inheritance capability，不是 public observe history。
- 对 public no-key caller，`visible` 指 [spec_observe_collaboration_cn.md](spec_observe_collaboration_cn.md) 定义的 public inheritance visibility：从 public project context 评估的当前 project visibility policy 与 source experiment stored visibility upper bound 的交集。
- Public inheritance visibility 不使用 raw experiment token，但仍尊重 source experiment stored visibility upper bound，因此 public `--from-exp` 不能扩展到 source experiment 创建时 narrowing 之外的访问范围。
- Archived source experiment 即使可按 id 显示，也需要 root/admin 才能作为 `--from-exp` 来源。
- `latest` 优先 resolve 到 source experiment latest run commit，没有 run 时 resolve branch HEAD。
- `final` 要求 final commit。
- `best` resolve 到 best passed run，并要求 parsed numeric reward。
- `--from-commit <sha>` 只接受 full 或 unambiguous commit SHA，且该 commit 必须从 source experiment branch 可达。
- New experiment 的 baseline commit 是 source commit 或 resolved experiment commit。
- 对 `--from-exp`，new experiment 存 source experiment 的 `source_id` 作为 source lineage，存 resolved experiment commit 为 `baseline_commit`，并在 `experiments.metadata_json` 记录 `from_exp` selector。它不创建新的 source row 或 source ref。
- Mutable override 只能收窄不能扩展。ALab 保存 experiment override，并在每次 run/submit scope check 时把 effective mutable policy 计算为 experiment 创建时绑定的 project policy 与 experiment override 的交集。
- Visibility override 只能收窄不能扩展。Experiment 创建时，ALab 将 current project visibility policy 与 requested visibility override 的交集 normalize 后保存为 experiment visibility upper bound。
- Creation tags normalize 为 lowercase ASCII slug，最长 64 bytes。
- ALab 在 creation 时保存 active valid project state 的 `bound_config_version` 和 `bound_validation_id`。
- ALab 创建 branch `alab/exp/<exp_id>`、worktree、context/token，为 `.alab/` 写入 worktree-local Git exclude rule，并存 experiment metadata。

Archive/unarchive：

- `exp archive` 需要 root/admin。
- Active run/submit lock 存在时 archive 以 `RESOURCE_BUSY` 失败。
- Archive 不删除 branches、commits、run records、artifacts、annotations、tags、source refs、final submission metadata。
- Archive 存 pre-archive status。
- `exp unarchive` 恢复 pre-archive status。
- `exp remove` 要求 experiment 已 archived，并遵循 [spec_lifecycle.md](spec_lifecycle.md) 中的 cascade 和 audit 规则。

Inspection checkout：

```text
alab exp checkout <exp_id> [--project <project_id>] --path <dir> [--commit final|latest|best|<sha>]
```

- 创建 inspection worktree、inspection marker、inspection token。
- Inspection checkout 是 CLI-read-only，不是 filesystem-read-only。
- 使用 detached HEAD at resolved inspection commit。
- Checkout 后即使本地文件 dirty，`status`、`observe`、artifact export 仍使用 pinned inspection commit 和 stored records。
- 继续工作需用 `alab exp create --from-exp <exp_id>`。

## 6. Worktree Maintenance

Commands：

```text
alab exp worktree remove <exp_id> [--project <project_id>] (--dry-run|--force --confirm <exp_id>) [--reason <text>]
alab exp worktree restore <exp_id> [--project <project_id>] --path <dir>
```

规则：

- 两个命令都需要 root/admin。
- `remove` 可在 experiment 为 open、closed 或 archived 时执行。
- `remove --dry-run` 报告 registered path、可获取时的 dirty state、token revocation target 和 planned trash move，不删除文件、不修改 DB、不写 audit row。
- `remove` unregister worktree path，将 path registry row 标记为 `removed`，revoke active worktree token，并设置 `worktree_state = 'removed'`。
- `--force --confirm <exp_id>` 是必需的；`--force` 是显式丢弃 uncommitted local files。
- `remove` 不删除 branch、run record、artifact、log、annotation、submission。
- `restore` 必须有 `--path`。
- Restore path 必须不存在或为空，且不得 nest 在其他 registered context 内。
- `restore` checkout experiment branch HEAD，写 `.alab/context.json`，revoke old active worktree token，创建新 worktree token，写 raw token 到 `.alab/token`，并为 `.alab/` 写入 worktree-local Git exclude rule。
- `restore` 设置 `worktree_state = 'active'`。
- Restore 绝不打印 raw token。

## 7. Mutable Scope

规则：

- Pattern 是 repo-relative。
- Path separator normalize 为 `/`。
- Pattern syntax 使用 pathspec GitWildMatchPattern semantics，以确保 `**`、anchoring 和 separator behavior 稳定。
- Include 定义 candidate writable paths。
- Exclude 移除 paths，且 exclude wins。
- `.alab/**` 始终 excluded。
- 规则适用于 added、modified、deleted、renamed、copied、type-changed paths。
- Added 和 modified paths 按 new path 校验。Deleted paths 按 old path 校验。Renames 和 copies 要求 source path 和 destination path 都被 effective mutable policy 允许。
- Matching 基于 repo-relative Git paths。
- Symlink entry 按 Git 中存储的 symlink path 管理，不 resolve target。
- V1 允许 source 和 experiment commits 中存在 Git symlink；这是 Git fidelity，不是 OS sandbox guarantee。

Experiment mutable override：

- 可减少 include coverage。
- 可增加 excludes。
- 不得增加 project policy 之外的 writable paths。
- 无 override 时使用 project policy。
- Effective mutable policy 通过 deterministic intersection 计算：path 只有同时被 project policy 和 experiment override 允许时才 writable。任一侧的 exclude 都优先。这避免了静态证明两个 GitWildMatch pattern set 子集关系的需求。

## 8. Run Lifecycle

Command：

```text
alab run --message <message>
```

规则：

- 必须在 experiment context 内运行。
- 需要 valid worktree token。
- Project 不得 archived。
- Experiment 必须 `open`。
- Experiment `worktree_state` 必须为 `active`。
- 使用 experiment bound valid config version。
- `--message` required，UTF-8 编码后最多 300 bytes。
- 同一 experiment 有 active run/submit 时快速以 `EXPERIMENT_BUSY` 失败。

Git state：

- HEAD 必须 attached 到 registered `alab/exp/<exp_id>` branch。
- Detached HEAD、不同 branch、merge/rebase/cherry-pick/bisect/unresolved conflict state 在 staging 前失败。
- ALab 检查 staged、unstaged、deleted、renamed、copied、untracked non-ignored changes。
- 每个 changed path 必须被 effective mutable policy 允许。
- ALab stages all allowed changed paths。
- 若 staged content 存在，ALab 创建一个 `ALab run: <message>` commit。
- Auto commit 包含所有 mutable-allowed staged、unstaged、deleted、renamed、copied 和 untracked non-ignored changes。ALab 不把 caller 原有 staged set 保留为独立概念。
- Manual commits 允许，只要 HEAD 在 registered branch 且 baseline 到 HEAD 的 full diff 被 mutable scope 允许。
- 如果 HEAD 已包含合法 manual commits 且 worktree 也有 dirty changes，ALab 先验证 experiment baseline commit 到 current HEAD 的 full diff，再 stage 并 auto-commit dirty changes，最后对新的 target commit 重复 full-diff mutable check。
- 已 staged changes 与 unstaged/untracked changes 一起参与 mutable-scope inspection 和 auto commit。
- 无 changes 时不创建 commit，run 指向 current HEAD。

Run execution flow：

1. Resolve experiment and token。
2. Validate project and experiment state。
3. Acquire experiment run/submit lock。
4. Check branch and Git operation state。
5. Check mutable scope for dirty changes。
6. Allocate `run_id` and create `running` run record。
7. Stage and commit if needed, using run id in trailers。
8. Check full-diff mutable scope。
9. 如果 full-diff scope 在 ALab auto commit 后失败，用 mixed-reset semantics 只 roll back 该 auto commit，将 file changes 保留为 unstaged worktree changes，在 run record 记录 rolled-back commit hash 和 explanation，标记 run `error`，渲染 `SCOPE_VIOLATION` details 和 next action，并释放 lock。
10. 如果 full-diff scope 因 existing manual commit 或 ALab 无法安全回滚的状态失败，保持 HEAD 和 worktree 不变，在 run record 记录 violation paths 和 explanation，标记 run `error`，渲染 `SCOPE_VIOLATION` details 和 next action，并释放 lock。
11. Create clean temporary `workspace` checkout。
12. 确保 temporary `workspace` 不包含 `.alab/context.json` 或 `.alab/token`；runner 不得通过 checkout 获得 submit-capable worktree token。
13. Create empty temporary `run_dir`。
14. Execute runner with bound config version and closed stdin。
15. Attempt reward extraction, including non-zero exit。
16. Capture logs and artifacts。
17. Update run record from `running` to final status。
18. Update experiment latest run and latest commit。
19. Release experiment lock。

Commit trailers：

- ALab 创建 commit 前先分配 run id。
- Auto commit subject 是 `ALab run: <message>`。
- Auto commit body 包含 `ALab-Run`、`ALab-Experiment`、`ALab-Config-Version` trailers。
- Git author 和 committer 来自 bound `[git]` config。

Run record：

- Auto commit 前必须写 `running` run record。
- Runner execution 前创建的 failed/error/timeout runs 不 rollback commit。
- 同一 commit 可有多个 run records。
- Ranking 使用 parsed numeric reward，不按 commit 唯一。
- 后续 run/submit/archive 前 stale `running` records 标记为 `interrupted`。
- Run archive、unarchive 和 remove 行为定义在 [spec_lifecycle.md](spec_lifecycle.md)。

## 9. Submit Lifecycle

Command：

```text
alab submit --message <message> --summary <text>|--summary-file <path> --feedback <text>|--feedback-file <path> --ref <exp_id|none> [--ref <exp_id> ...] [--rerun]
```

规则：

- 必须在 experiment context 中并带 valid worktree token。
- Project 不得 archived。
- Experiment 必须 `open`。
- Experiment `worktree_state` 必须为 `active`。
- `--message`、summary、feedback 和至少一个 `--ref` required。
- Summary direct text 与 `--summary-file` 二选一。
- Feedback direct text 与 `--feedback-file` 二选一。
- Summary/feedback file 相对当前 command cwd 解析。
- V1 不支持 `--summary-stdin` 或 `--feedback-stdin`。
- `--ref none` 与 experiment refs 互斥。
- Experiment refs 按 first-seen order 去重。
- 每个 `--ref <exp_id>` 必须对 submitting token/caller 可见。
- Invisible refs 失败时不泄露额外 record details。
- Submit message、summary 和 feedback UTF-8 编码后分别最多 300、65536 和 65536 bytes。
- Summary 和 feedback 不得包含 experiment bound config version 下 active `secret_env` values 的 exact match。发现 exact secret value 时，submit fail，且不存 final submission text。
- `--rerun` 存在时始终执行 run flow。
- Worktree 有 changes 时执行 run flow。
- 当 submit 执行 run flow 时，复用 `submit --message` 作为 run message。该 run 创建的 automatic commit 仍使用正常的 `ALab run: <message>` subject，submission row 也单独保存同一个 submit message。
- 无 changes 时，仅当 current HEAD 和 experiment bound config version 的 most recent run 为 `passed` 时复用。
- 无 changes 且无 reusable passed run 时，submit exit `1` 并提示用 `--rerun`。
- Final run `passed` 时创建一条 `experiment_submissions` row，保存 message、summary、feedback、refs、final commit、final run id，并关闭 experiment。
- Final run 非 `passed` 时保持 experiment open，不存 final summary/feedback/refs/final commit/final run id；run record 保留。
