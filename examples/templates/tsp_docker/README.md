# TSP Docker Template

Copy this directory when you want the same TSP task evaluated inside a Docker
container built from `source/Dockerfile`.

## Use When

- You need containerized dependencies or an isolated runtime.
- You want the Dockerfile runner with `network = "none"`.
- You want file reward outputs and route artifacts from inside the container.

## Commands

```sh
scripts/setup_project.sh --dry-run
scripts/setup_project.sh
scripts/run_demo.sh
```

Docker must be installed and running. The template uses `python:3.11-alpine`.
Use `scripts/setup_project.sh --reset` to recreate `.run/`. Set
`ALAB_REPO_ROOT=/path/to/ALab` after copying the template outside this
repository. Set `ALAB_BIN` only for a custom `alab` command; quote arguments
that contain spaces.

## Files To Edit

- `source/solution.py`: implement `build_route(cities) -> list[int]`.
- `source/Dockerfile`: container image for the runner.
- `source/validate_tsp.py`: verifier and artifact writer.
- `alab.project.toml`: Docker runner, reward, artifact, and visibility config.

Generated project state stays under `.run/`, and project admin keys stay under
`.run/secrets/`.
