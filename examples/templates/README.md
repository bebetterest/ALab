# ALab TSP Templates

The `examples/templates/` directory contains copyable starter projects for a
single Traveling Salesperson Problem task across every ALab V1 runner family.
Each template is self-contained, keeps generated state in its own ignored
`.run/` directory, and stores project admin keys only under `.run/secrets/`.

## Demo Task

Every template uses the same deterministic multi-instance TSP task. Edit
`solution.py` so `build_route(cities)` returns a valid closed tour for one city
list. The evaluator calls it once per instance across 15 fixed generated
instances: five 100-city instances, five 500-city instances, and five 1000-city
instances. It checks that every route is a complete permutation, computes each
Euclidean closed-tour length, and minimizes `total_tour_length`, the sum across
all instances.

The starter solution is intentionally a poor baseline: it returns the cities in
file order with `list(range(len(cities)))`. On the bundled benchmark that
baseline measures about `42000612.353972`. The demo scripts change one flag to
enable a deterministic nearest-neighbor improvement, then run ALab and submit
the passed experiment.

For a stronger reference, copy
[`reference_solution/solution.py`](reference_solution/solution.py) over a
template worktree's editable `solution.py`. This is a deterministic reference
target, not a claim of global optimality. It should reach
`total_tour_length <= 2650000` with all 15 instances valid.

## Template Matrix

| Template | Runner / adapter | Extra requirements | Primary files | Command |
| --- | --- | --- | --- | --- |
| [tsp_local](tsp_local/) | local | none beyond the ALab dev env | `source/solution.py`, `source/validate_tsp.py`, `alab.project.toml` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_docker](tsp_docker/) | Docker | Docker daemon and `python:3.11-alpine` | `source/Dockerfile`, `source/solution.py`, `source/validate_tsp.py` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_harbor](tsp_harbor/) | Harbor | Docker daemon and `python:3.11-alpine` | `task/starter/solution.py`, `task/tests/test.sh`, `alab.project.template.toml` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_skydiscover_python](tsp_skydiscover_python/) | SkyDiscover Python | none beyond the ALab dev env | `source/solution.py`, `evaluator/evaluator.py`, `alab.project.template.toml` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_skydiscover_docker](tsp_skydiscover_docker/) | SkyDiscover Docker | Docker daemon and `python:3.11-alpine` | `source/solution.py`, `evaluator/Dockerfile`, `evaluator/evaluate.sh` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |

## Reference Target

The shared benchmark is deliberately larger than the starter: 8000 total cities
across 15 instances. Use these guideposts when comparing runs:

| Solution | Expected `total_tour_length` | Notes |
| --- | ---: | --- |
| Starter baseline | about `42000612.353972` | Sequential route; valid but intentionally weak. |
| Demo nearest-neighbor flag | about `2977646.521360` | Fast deterministic improvement used by `run_demo.sh`. |
| `reference_solution/solution.py` | at most `2650000` | Strong deterministic reference; not claimed to be globally optimal. |

## Run A Template

Run from the repository root, or set `ALAB_REPO_ROOT` when running a copied
template outside this checkout.

```sh
examples/templates/tsp_local/scripts/setup_project.sh --dry-run
examples/templates/tsp_local/scripts/setup_project.sh
examples/templates/tsp_local/scripts/run_demo.sh
```

Docker-backed templates use the same command shape but require a working Docker
daemon:

```sh
examples/templates/tsp_docker/scripts/setup_project.sh
examples/templates/tsp_harbor/scripts/setup_project.sh
examples/templates/tsp_skydiscover_docker/scripts/setup_project.sh
```

Adapter templates with local task/evaluator paths keep tracked configs
portable by using `alab.project.template.toml`. Their setup scripts render a
generated `.run/generated/alab.project.toml` with the absolute local path before
calling `alab project init`.

## Copying

Copy one template directory, keep the `source/` or `task/starter/` public files
as the worker-editable surface, then adjust the project name, task text, data,
and evaluator logic. The bundled data lives in `instances.json`; it stores the
fixed instance sizes and seeds used by the deterministic coordinate generator.
Keep reward JSON files as string-to-finite-number maps. Put route diagnostics,
explanations, and hidden verifier details in artifacts, logs, or SkyDiscover
feedback instead of reward JSON.

## Isolation Notes

Setup scripts may write a project admin key to `.run/secrets/project.env`.
Worker commands should use the experiment worktree token and must not receive
`.run/secrets/`, root keys, project admin keys, or generated config files that
contain local secret material.
