# TSP SkyDiscover Docker Template

Copy this directory when you want the TSP task evaluated by a local
SkyDiscover-style Docker evaluator bundle.

## Use When

- You want SkyDiscover evaluator semantics with containerized evaluator logic.
- You need hidden evaluator execution with `network = "none"`.
- You want the public editable source passed with `--source-path source`.

## Commands

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

Docker must be installed and running. The setup script renders
`.run/generated/alab.project.toml` from `alab.project.template.toml` so copied
templates do not commit machine-specific evaluator paths. Set
`ALAB_REPO_ROOT=/path/to/ALab` after copying the template outside this
repository. Set `ALAB_BIN` only for a custom `alab` command; quote arguments
that contain spaces.

## Files To Edit

- `source/solution.py`: implement `build_route(cities) -> list[int]`.
- `source/instances.json`: deterministic benchmark sizes and seeds.
- `evaluator/Dockerfile`: container image for the evaluator.
- `evaluator/evaluate.sh`: evaluator entrypoint; stdout is evaluator JSON.
- `evaluator/evaluator.py`: evaluator implementation.
- `alab.project.template.toml`: portable SkyDiscover runner config template.

Generated project state stays under `.run/`, and project admin keys stay under
`.run/secrets/`.
