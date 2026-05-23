# Local Agent Scoreboard Example

This example demonstrates ALab's local runner with a small deterministic Python
candidate. It is the fastest example for checking the normal project, run,
artifact, and submit loop.

## Demo Task

Improve `source/solution.py` so it reports a higher deterministic score,
captures `score.json`, and submits the best run. The manual demo edits the
candidate from a baseline strategy to a deterministic improvement; the optional
Codex worker follows the same task inside a narrow experiment worktree.

Task shape:

- Editable file: `source/solution.py`.
- Baseline behavior: `SCORE = 0.40`, printed as `reward=0.400`.
- Demo improvement: `scripts/run_manual_demo.sh` changes the strategy and score
  to `0.82`, then runs and submits the candidate.
- Reward source: stdout regex `reward=([0-9.]+)`.
- Captured evidence: `run:score.json` plus the workspace copy of
  `solution.py`.

This example is intentionally small. It is the best place to inspect how ALab
creates an experiment worktree, writes a worktree token, captures logs and
artifacts, and closes an experiment with `alab submit`.

## What It Covers

- local runner with sanitized environment;
- stdout regex reward parsing;
- run artifact capture from `ALAB_RUN_DIR`;
- worktree-token run and submit;
- optional Codex worker launch with a narrow sandbox.

## Run

From the repository root:

```sh
examples/local_agent_scoreboard/scripts/setup_project.sh --dry-run
examples/local_agent_scoreboard/scripts/setup_project.sh
examples/local_agent_scoreboard/scripts/run_manual_demo.sh
```

Optional Codex worker:

```sh
examples/local_agent_scoreboard/scripts/run_codex_worker.sh --dry-run
examples/local_agent_scoreboard/scripts/run_codex_worker.sh
```

Generated state stays under ignored `.run/`. The project admin key is stored
only in `.run/secrets/project.env`; Codex workers are not given that directory.

## Isolation Notes

The Codex worker command uses the experiment worktree as `-C`; that worktree is
the only editable source surface. The script preflights that the worktree is not
the repository root, `.run`, or `.run/secrets`, then adds only ALab home, uv
cache, pycache, and `.run/shared` as writable CLI state directories. It does not
add the repository root, the whole `.run/` directory, `.run/secrets`, or
`project.env`.
