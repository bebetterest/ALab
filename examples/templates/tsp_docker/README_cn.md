# TSP Docker Template

当你希望同一套 TSP task 在 Docker container 中评分时，复制这个目录即可；
container 由 `source/Dockerfile` 构建。

## 适用场景

- 需要容器化依赖或隔离 runtime。
- 需要使用 `network = "none"` 的 Dockerfile runner。
- 希望从容器中产出 file reward 和 route artifacts。

## 命令

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

需要已安装并启动 Docker。模板使用 `python:3.11-alpine`。使用
`scripts/setup_project.sh --reset` 可以重建 `.run/`。复制到仓库外运行时，设置
`ALAB_REPO_ROOT=/path/to/ALab`。只有需要自定义 `alab` 命令时才设置 `ALAB_BIN`；
包含空格的参数需要加 shell quote。

## 可编辑文件

- `source/solution.py`：实现 `build_route(cities) -> list[int]`。
- `source/Dockerfile`：runner 使用的 container image。
- `source/validate_tsp.py`：verifier 和 artifact writer。
- `alab.project.toml`：Docker runner、reward、artifact 和 visibility 配置。

生成的 project 状态只写入 `.run/`，project admin key 只写入 `.run/secrets/`。
