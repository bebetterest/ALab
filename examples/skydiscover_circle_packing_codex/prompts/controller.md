# Codex Controller Prompt: 3-Step ALab Circle Packing Protocol

You are the controller for the ALab SkyDiscover Circle Packing example.

You have access to the project admin key through the environment variable
`ALAB_PROJECT_KEY`. Do not print it. Do not write it into logs, prompts, commits, or
final summaries.

Required protocol:

1. Use the `ALAB_*` helper variables already provided in the controller
   environment. Do not read `.run/secrets/project.env` from inside Codex.
2. Create `codex-circle-step-1` from the project default source.
3. Launch one Codex worker in the Step 1 worktree using
   `examples/skydiscover_circle_packing_codex/prompts/worker.md`.
4. Inspect the Step 1 result with ALab observe commands.
5. Create `codex-circle-step-2` from Step 1 using `--from-exp <step-1-exp-id>
   --from-commit best`.
6. Launch one worker in the Step 2 worktree.
7. Inspect the Step 2 result.
8. Create `codex-circle-step-3` from Step 2 using `--from-exp <step-2-exp-id>
   --from-commit best`.
9. Launch one worker in the Step 3 worktree.
10. Run `examples/skydiscover_circle_packing_codex/scripts/collect_report.sh`.

Use this ALab command pattern for admin commands:

```sh
eval "$ALAB_CMD_PREFIX --key \"\$ALAB_PROJECT_KEY\" <command>"
```

Use this worker-launch pattern, replacing `<worktree>` with the created worktree
path:

```sh
CODEX_MODEL_ARGS=()
if [ -n "${CODEX_MODEL:-}" ]; then
  CODEX_MODEL_ARGS=(-m "$CODEX_MODEL")
fi

env -u ALAB_PROJECT_KEY \
  ALAB_CMD_PREFIX="$ALAB_CMD_PREFIX" \
  codex exec -C "<worktree>" \
  --add-dir "$ALAB_EXAMPLE_HOME" \
  --add-dir "$UV_CACHE_DIR" \
  --add-dir "$PYTHONPYCACHEPREFIX" \
  --add-dir "$ALAB_SHARED_DIR" \
  "${CODEX_MODEL_ARGS[@]}" \
  --sandbox workspace-write \
  - < examples/skydiscover_circle_packing_codex/prompts/worker.md
```

Constraints:
- Never expose `ALAB_PROJECT_KEY`.
- Worker processes must run without `ALAB_PROJECT_KEY`.
- Do not give workers the repository root, the whole `.run/` directory,
  `.run/secrets`, or `project.env`.
- Each worker should run one ALab evaluation.
- If a step fails, record the failure in the report log and continue only when a
  safe next action is clear.
- The final response should summarize best score, best experiment, and report path.
