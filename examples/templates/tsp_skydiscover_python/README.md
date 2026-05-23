# TSP SkyDiscover Python Template

Copy this directory when you want the TSP task evaluated by a local
SkyDiscover-style Python evaluator without using a remote catalog.

## Use When

- You want SkyDiscover evaluator semantics with no Docker requirement.
- You want a local `evaluator/evaluator.py` that exposes `evaluate(program_path)`.
- You want the public editable source passed with `--source-path source`.

## Commands

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

The setup script renders `.run/generated/alab.project.toml` from
`alab.project.template.toml` so copied templates do not commit
machine-specific evaluator paths. Set `ALAB_REPO_ROOT=/path/to/ALab` after
copying the template outside this repository. Set `ALAB_BIN` only for a custom
`alab` command; quote arguments that contain spaces.

## Files To Edit

- `source/solution.py`: implement `build_route(cities) -> list[int]`.
- `source/instances.json`: deterministic benchmark sizes and seeds.
- `evaluator/evaluator.py`: SkyDiscover Python evaluator.
- `alab.project.template.toml`: portable SkyDiscover runner config template.

Generated project state stays under `.run/`, and project admin keys stay under
`.run/secrets/`.
