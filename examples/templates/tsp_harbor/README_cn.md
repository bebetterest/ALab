# TSP Harbor Template

当你希望把 TSP task 打包为 Harbor-style task 时，复制这个目录即可：
public starter files 放在 `task/starter/`，hidden verifier 放在
`task/tests/test.sh`。

## 适用场景

- 需要模拟 hidden-test benchmark。
- 需要 Harbor reward parsing 和 hidden verifier logs。
- 希望 worker 只编辑 starter `solution.py`。

## 命令

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

需要已安装并启动 Docker。setup 脚本会从 `alab.project.template.toml` 生成
`.run/generated/alab.project.toml`，避免复制模板后把机器相关 task path 提交进仓库。
复制到仓库外运行时，设置 `ALAB_REPO_ROOT=/path/to/ALab`。只有需要自定义 `alab`
命令时才设置 `ALAB_BIN`；包含空格的参数需要加 shell quote。

## 可编辑文件

- `task/starter/solution.py`：实现 `build_route(cities) -> list[int]`。
- `task/starter/instances.json`：deterministic benchmark 的 size 和 seed。
- `task/tests/test.sh`：hidden verifier 和 reward writer。
- `task/instruction.md`：面向 worker 的任务说明。
- `alab.project.template.toml`：portable Harbor runner config template。

生成的 project 状态只写入 `.run/`，project admin key 只写入 `.run/secrets/`。
