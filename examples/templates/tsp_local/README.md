# TSP Local Template

Copy this directory when you want the smallest default ALab project: a local
runner that executes `python validate_tsp.py` against the editable
`source/solution.py`.

## Use When

- You want a no-Docker starter project.
- You want visible file reward outputs in `run:reward.json`.
- You are testing the TSP task contract before moving it to a container or
  adapter runner.

## Commands

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

Use `scripts/setup_project.sh --reset` to recreate the isolated `.run/` state.
Set `ALAB_REPO_ROOT=/path/to/ALab` after copying the template outside this
repository. Set `ALAB_BIN` only when you need a custom `alab` command; quote
arguments that contain spaces.

## Files To Edit

- `source/solution.py`: implement `build_route(cities) -> list[int]`.
- `source/instances.json`: deterministic benchmark sizes and seeds.
- `source/validate_tsp.py`: local verifier and artifact writer.
- `alab.project.toml`: local runner, reward, artifact, and visibility config.

Generated project state stays under `.run/`, and project admin keys stay under
`.run/secrets/`.
