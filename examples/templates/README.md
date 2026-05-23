# ALab TSP Templates

The `examples/templates/` directory contains copyable starter projects for a
single Traveling Salesperson Problem task across every ALab V1 runner family.
Each template is self-contained, keeps generated state in its own ignored
`.run/` directory, and stores project admin keys only under `.run/secrets/`.

## Demo Task

Every template uses the same deterministic TSP task. Edit `solution.py` so
`build_route(cities)` returns a valid closed tour over the provided city list.
The evaluator checks that the route is a complete permutation, computes the
Euclidean closed-tour length, and maximizes a stable score derived from
`1 / tour_length`.

The starter solution returns the cities in file order. The demo scripts change
one flag to enable a deterministic 2-opt improvement, then run ALab and submit
the passed experiment.

## Template Matrix

| Template | Runner / adapter | Extra requirements | Primary files | Command |
| --- | --- | --- | --- | --- |
| [tsp_local](tsp_local/) | local | none beyond the ALab dev env | `source/solution.py`, `source/validate_tsp.py`, `alab.project.toml` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_docker](tsp_docker/) | Docker | Docker daemon and `python:3.11-alpine` | `source/Dockerfile`, `source/solution.py`, `source/validate_tsp.py` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_harbor](tsp_harbor/) | Harbor | Docker daemon and `python:3.11-alpine` | `task/starter/solution.py`, `task/tests/test.sh`, `alab.project.template.toml` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_skydiscover_python](tsp_skydiscover_python/) | SkyDiscover Python | none beyond the ALab dev env | `source/solution.py`, `evaluator/evaluator.py`, `alab.project.template.toml` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |
| [tsp_skydiscover_docker](tsp_skydiscover_docker/) | SkyDiscover Docker | Docker daemon and `python:3.11-alpine` | `source/solution.py`, `evaluator/Dockerfile`, `evaluator/evaluate.sh` | `scripts/setup_project.sh`, `scripts/run_demo.sh` |

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
and evaluator logic. Keep reward JSON files as string-to-finite-number maps.
Put route diagnostics, explanations, and hidden verifier details in artifacts,
logs, or SkyDiscover feedback instead of reward JSON.

## Isolation Notes

Setup scripts may write a project admin key to `.run/secrets/project.env`.
Worker commands should use the experiment worktree token and must not receive
`.run/secrets/`, root keys, project admin keys, or generated config files that
contain local secret material.
