# Codex Worker Prompt: ALab SkyDiscover Circle Packing

You are inside one ALab experiment worktree for the SkyDiscover
`benchmarks/math/circle_packing` task.

Goal: improve the candidate in `initial_program.py` and run exactly one ALab evaluation.

Rules:
- Edit only `initial_program.py`.
- Keep the public contract: `run_packing()` returns `(centers, radii, sum_radii)`.
- The solution must describe exactly 26 circles in the unit square.
- Do not edit `.alab/`, do not print tokens, and do not use a project admin key.
- Prefer deterministic geometry changes over broad rewrites.
- Keep the implementation readable enough for a later worker to continue from it.

Useful local checks:

```sh
python initial_program.py
```

Run the ALab evaluation from this worktree with:

```sh
eval "$ALAB_CMD_PREFIX run --message 'codex circle-packing worker improvement'"
```

After the run, report:
- what geometric strategy changed,
- the run id,
- run status,
- reward / `combined_score`,
- any metric names shown by ALab.
