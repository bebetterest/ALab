# TSP Local Template

当你需要最小的默认 ALab project 时，复制这个目录即可：它使用 local
runner，执行 `python validate_tsp.py`，评分可编辑的 `source/solution.py`。

## 适用场景

- 需要不依赖 Docker 的 starter project。
- 希望通过 `run:reward.json` 查看 file reward 输出。
- 在迁移到容器或 adapter runner 前，先验证 TSP task contract。

## 命令

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

使用 `scripts/setup_project.sh --reset` 可以重建隔离的 `.run/` 状态。复制到仓库外
运行时，设置 `ALAB_REPO_ROOT=/path/to/ALab`。只有需要自定义 `alab` 命令时才设置
`ALAB_BIN`；包含空格的参数需要加 shell quote。

## 可编辑文件

- `source/solution.py`：实现 `build_route(cities) -> list[int]`。
- `source/instances.json`：deterministic benchmark 的 size 和 seed。
- `source/validate_tsp.py`：local verifier 和 artifact writer。
- `alab.project.toml`：local runner、reward、artifact 和 visibility 配置。

生成的 project 状态只写入 `.run/`，project admin key 只写入 `.run/secrets/`。
