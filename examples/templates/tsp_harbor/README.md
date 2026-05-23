# TSP Harbor Template

Copy this directory when you want the TSP task packaged as a Harbor-style task:
public starter files under `task/starter/` and a hidden verifier under
`task/tests/test.sh`.

## Use When

- You want to model a hidden-test benchmark.
- You need Harbor reward parsing and hidden verifier logs.
- You want workers to edit only the starter `solution.py`.

## Commands

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

Docker must be installed and running. The setup script renders
`.run/generated/alab.project.toml` from `alab.project.template.toml` so copied
templates do not commit machine-specific task paths. Set
`ALAB_REPO_ROOT=/path/to/ALab` after copying the template outside this
repository. Set `ALAB_BIN` only for a custom `alab` command; quote arguments
that contain spaces.

## Files To Edit

- `task/starter/solution.py`: implement `build_route(cities) -> list[int]`.
- `task/starter/instances.json`: deterministic benchmark sizes and seeds.
- `task/tests/test.sh`: hidden verifier and reward writer.
- `task/instruction.md`: worker-facing task instructions.
- `alab.project.template.toml`: portable Harbor runner config template.

Generated project state stays under `.run/`, and project admin keys stay under
`.run/secrets/`.
