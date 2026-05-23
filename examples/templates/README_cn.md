# ALab TSP 模板

`examples/templates/` 目录提供一组可复制的 starter projects，用同一个
Traveling Salesperson Problem 任务覆盖 ALab V1 的所有 runner 家族。每个模板都
是自包含的，生成状态写入自身 ignored `.run/` 目录，project admin key 只保存到
`.run/secrets/`。

## Demo 任务

所有模板使用同一个 deterministic TSP 任务。修改 `solution.py`，让
`build_route(cities)` 返回覆盖所有城市的合法闭环 tour。evaluator 会检查 route
是否是完整 permutation，计算 Euclidean closed-tour length，并最大化由
`1 / tour_length` 得到的稳定 score。

starter solution 按文件顺序返回城市。demo scripts 会修改一个 flag，启用
deterministic 2-opt 改进，然后运行 ALab 并提交通过的 experiment。

## 模板矩阵

| 模板 | Runner / adapter | 额外要求 | 主要文件 | 命令 |
| --- | --- | --- | --- | --- |
| [tsp_local](tsp_local/) | local | ALab dev env 之外无额外要求 | `source/solution.py`、`source/validate_tsp.py`、`alab.project.toml` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_docker](tsp_docker/) | Docker | Docker daemon 和 `python:3.11-alpine` | `source/Dockerfile`、`source/solution.py`、`source/validate_tsp.py` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_harbor](tsp_harbor/) | Harbor | Docker daemon 和 `python:3.11-alpine` | `task/starter/solution.py`、`task/tests/test.sh`、`alab.project.template.toml` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_skydiscover_python](tsp_skydiscover_python/) | SkyDiscover Python | ALab dev env 之外无额外要求 | `source/solution.py`、`evaluator/evaluator.py`、`alab.project.template.toml` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |
| [tsp_skydiscover_docker](tsp_skydiscover_docker/) | SkyDiscover Docker | Docker daemon 和 `python:3.11-alpine` | `source/solution.py`、`evaluator/Dockerfile`、`evaluator/evaluate.sh` | `scripts/setup_project.sh`、`scripts/run_demo.sh` |

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
逻辑。reward JSON files 必须保持 string-to-finite-number map。route diagnostics、
解释和 hidden verifier details 应写入 artifacts、logs 或 SkyDiscover feedback，
不要放进 reward JSON。

## 隔离说明

setup scripts 可以把 project admin key 写入 `.run/secrets/project.env`。worker
commands 应使用 experiment worktree token，不能收到 `.run/secrets/`、root keys、
project admin keys，或包含本地 secret material 的 generated config files。
