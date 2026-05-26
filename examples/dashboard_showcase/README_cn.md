# Dashboard Showcase Home

本示例会生成一个内容丰富的本地 ALab home，用于查看 root-only dashboard。它不是
worker task walkthrough，而是把多个 projects、experiments、runs、logs、
artifacts、annotations、audit events、feedback entries、caches、capabilities、
catalogs 和 locks 写入同一个 home，让 dashboard 有接近真实使用痕迹的数据可浏览。

生成状态保存在 ignored `.run/` 目录下。

## Demo 任务

生成一个只用于 inspection 的 ALab home，用于演示 root dashboard，而不要求 Docker、
SkyDiscover、Harbor 或外部 worker。生成的 rows 旨在让 dashboard filters、project
detail pages、reward charts、hidden logs、artifact previews、feedback、audit 和
system panels 都有足够数据可查看。

## 生成 Home

从仓库根目录运行：

```bash
UV_CACHE_DIR=examples/dashboard_showcase/.run/uv-cache \
UV_DEFAULT_INDEX=https://pypi.org/simple \
uv run --locked python examples/dashboard_showcase/scripts/create_demo_home.py --force
```

脚本会输出：

- `home`：生成的 ALab home 路径。
- `root_key`：这个 demo home 的 root key。
- `credentials_file`：ignored 文件，包含生成的 root/admin/token keys。
- `dashboard_command`：可直接运行的 dashboard 命令。

默认生成路径是：

```text
examples/dashboard_showcase/.run/alab-home
```

## 打开 Dashboard

生成 home 后运行：

```bash
examples/dashboard_showcase/scripts/run_dashboard.sh --no-open
```

也可以复制 generator 输出的 `dashboard_command`。Dashboard 只绑定
`127.0.0.1`，并在 URL 中使用 temporary browser token。

## Seed 数据覆盖

生成的 home 包含：

- 四个 projects：valid Docker-style clinic planner、valid Harbor-style
  incident classifier、invalid SkyDiscover Python project，以及 archived local
  baseline project。
- Open、closed、archived experiments，以及 active/removed worktree registry rows。
- Passed、failed、error、timeout、interrupted、active 和 archived run traces。
- Maximize 与 minimize 两种 reward direction 的 reward trends。
- 可见 stdout/stderr logs，以及 hidden verifier/evaluator logs。
- Captured text、JSON、PNG artifacts，以及 skipped/error artifact rows。
- Final submissions、experiment tags、annotations、audit events、feedback
  entries、runtime capabilities、SkyDiscover catalog state、cache entries 和
  active lock row。

## 安全说明

所有 keys 和 secret values 都在本地 ignored `.run/` 下生成。不要把它们复制到
committed files。本示例只用于 local dashboard inspection。
