# ALab TSP 模板

`examples/templates/` 目录提供一组可复制的 starter projects，用同一个
Traveling Salesperson Problem 任务覆盖 ALab V1 的所有 runner 家族。每个模板都
是自包含的，生成状态写入自身 ignored `.run/` 目录，project admin key 只保存到
`.run/secrets/`。

## Demo 任务

所有模板使用同一个 deterministic multi-instance TSP 任务。修改
`solution.py`，让 `build_route(cities)` 针对单个城市列表返回合法闭环 tour。
evaluator 会在 15 组固定生成实例上逐组调用它：5 组 100-city、5 组
500-city、5 组 1000-city。它会检查每条 route 是否是完整 permutation，计算每组
Euclidean closed-tour length，并最小化 `total_tour_length`，也就是所有实例的
路径长度和。

starter solution 是故意很差的 baseline：它用 `list(range(len(cities)))`
按文件顺序返回城市。在内置 benchmark 上 baseline 约为 `42000612.353972`。
demo scripts 会修改一个 flag，启用 deterministic nearest-neighbor 改进，然后运行
ALab 并提交通过的 experiment。

更强的参考目标可以使用
[`reference_solution/solution.py`](reference_solution/solution.py)：把它复制到
某个 template worktree 中可编辑的 `solution.py` 上。这是 deterministic reference
target，不表示全局最优保证。它应能在全部 15 组实例合法的前提下达到
`total_tour_length <= 2650000`。

## 模板矩阵

| 模板 | Runner / adapter | 额外要求 | 主要文件 | 命令 |
| --- | --- | --- | --- | --- |
| [tsp_local](tsp_local/) | local | ALab dev env 之外无额外要求 | `source/solution.py`、`source/validate_tsp.py`、`alab.project.toml` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_docker](tsp_docker/) | Docker | Docker daemon 和 `python:3.11-alpine` | `source/Dockerfile`、`source/solution.py`、`source/validate_tsp.py` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_harbor](tsp_harbor/) | Harbor | Docker daemon 和 `python:3.11-alpine` | `task/starter/solution.py`、`task/tests/test.sh`、`alab.project.template.toml` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_skydiscover_python](tsp_skydiscover_python/) | SkyDiscover Python | ALab dev env 之外无额外要求 | `source/solution.py`、`evaluator/evaluator.py`、`alab.project.template.toml` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_skydiscover_docker](tsp_skydiscover_docker/) | SkyDiscover Docker | Docker daemon 和 `python:3.11-alpine` | `source/solution.py`、`evaluator/Dockerfile`、`evaluator/evaluate.sh` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |

## 参考目标

共享 benchmark 故意比 starter 大：15 组实例总计 8000 个城市。比较 run 时可使用
这些参考值：

| Solution | 预期 `total_tour_length` | 说明 |
| --- | ---: | --- |
| Starter baseline | 约 `42000612.353972` | Sequential route；合法但故意较弱。 |
| Demo nearest-neighbor flag | 约 `2977646.521360` | `run_demo.sh` 使用的快速 deterministic improvement。 |
| `reference_solution/solution.py` | 不高于 `2650000` | 强 deterministic reference；不声称全局最优。 |

## 运行模板

从仓库根目录运行；如果把模板复制到 checkout 外部运行，设置 `ALAB_REPO_ROOT`
指向 ALab 仓库。

```sh
examples/templates/tsp_local/scripts/setup_project.sh --dry-run
examples/templates/tsp_local/scripts/setup_project.sh
examples/templates/tsp_local/scripts/run_demo.sh
```

Docker-backed templates 使用相同命令形态，但需要可用 Docker daemon：

```sh
examples/templates/tsp_docker/scripts/setup_project.sh
examples/templates/tsp_harbor/scripts/setup_project.sh
examples/templates/tsp_skydiscover_docker/scripts/setup_project.sh
```

使用本地 task/evaluator path 的 adapter templates 通过
`alab.project.template.toml` 保持 tracked config 可移植。setup scripts 会先生成
`.run/generated/alab.project.toml`，把绝对本地路径注入后再调用
`alab project init`。

## 复制使用

复制任一 template 目录，把 `source/` 或 `task/starter/` 中的 public 文件作为
worker-editable surface，然后调整 project name、task text、数据和 evaluator
逻辑。内置数据在 `instances.json` 中；它保存 deterministic coordinate generator
使用的固定实例规模和 seeds。reward JSON files 必须保持
string-to-finite-number map。route diagnostics、解释和 hidden verifier details
应写入 artifacts、logs 或 SkyDiscover feedback，不要放进 reward JSON。

## 隔离说明

setup scripts 可以把 project admin key 写入 `.run/secrets/project.env`。worker
commands 应使用 experiment worktree token，不能收到 `.run/secrets/`、root keys、
project admin keys，或包含本地 secret material 的 generated config files。
