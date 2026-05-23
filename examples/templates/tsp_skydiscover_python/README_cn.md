# TSP SkyDiscover Python Template

当你希望使用本地 SkyDiscover-style Python evaluator 评分 TSP task，且不依赖远端
catalog 时，复制这个目录即可。

## 适用场景

- 需要 SkyDiscover evaluator 语义，但不希望依赖 Docker。
- 需要本地 `evaluator/evaluator.py` 暴露 `evaluate(program_path)`。
- 希望通过 `--source-path source` 传入 public editable source。

## 命令

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

setup 脚本会从 `alab.project.template.toml` 生成 `.run/generated/alab.project.toml`，
避免复制模板后把机器相关 evaluator path 提交进仓库。复制到仓库外运行时，设置
`ALAB_REPO_ROOT=/path/to/ALab`。只有需要自定义 `alab` 命令时才设置 `ALAB_BIN`；
包含空格的参数需要加 shell quote。

## 可编辑文件

- `source/solution.py`：实现 `build_route(cities) -> list[int]`。
- `source/instances.json`：deterministic benchmark 的 size 和 seed。
- `evaluator/evaluator.py`：SkyDiscover Python evaluator。
- `alab.project.template.toml`：portable SkyDiscover runner config template。

生成的 project 状态只写入 `.run/`，project admin key 只写入 `.run/secrets/`。
