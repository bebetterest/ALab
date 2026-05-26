# Dashboard Showcase Home

This example creates a rich local ALab home for inspecting the root-only
dashboard. It is not a task walkthrough for workers. Instead, it seeds one home
with multiple projects, experiments, runs, logs, artifacts, annotations, audit
events, feedback entries, caches, capabilities, catalogs, and locks so the
dashboard has realistic data to browse.

Generated state lives under ignored `.run/`.

## Demo Task

Generate an inspection-only ALab home that exercises the root dashboard without
requiring Docker, SkyDiscover, Harbor, or external workers. The generated rows
are designed to make dashboard filters, project detail pages, reward charts,
hidden logs, artifact previews, feedback, audit, and system panels easy to
inspect.

## Create The Home

From the repository root:

```bash
UV_CACHE_DIR=examples/dashboard_showcase/.run/uv-cache \
UV_DEFAULT_INDEX=https://pypi.org/simple \
uv run --locked python examples/dashboard_showcase/scripts/create_demo_home.py --force
```

The script prints:

- `home`: the generated ALab home path.
- `root_key`: the generated root key for this demo home.
- `credentials_file`: ignored file containing generated root/admin/token keys.
- `dashboard_command`: a ready-to-run command.

The default generated home is:

```text
examples/dashboard_showcase/.run/alab-home
```

## Open The Dashboard

After generating the home, run:

```bash
examples/dashboard_showcase/scripts/run_dashboard.sh --no-open
```

Or copy the `dashboard_command` printed by the generator. The dashboard binds
only to `127.0.0.1` and uses a temporary browser token in the URL.

## Seeded Coverage

The generated home includes:

- Four projects: a valid Docker-style clinic planner, a valid Harbor-style
  incident classifier, an invalid SkyDiscover Python project, and an archived
  local baseline project.
- Open, closed, and archived experiments with active and removed worktree
  registry rows.
- Passed, failed, error, timeout, interrupted, active, and archived run traces.
- Reward trends for both maximize and minimize reward directions.
- Visible stdout/stderr logs and hidden verifier/evaluator logs.
- Captured text, JSON, and PNG artifacts plus skipped and error artifact rows.
- Final submissions, experiment tags, annotations, audit events, feedback
  entries, runtime capabilities, SkyDiscover catalog state, cache entries, and
  an active lock row.

## Safety Notes

All keys and secret values are generated locally under ignored `.run/`. Do not
copy them into committed files. The example is intended for local dashboard
inspection only.
