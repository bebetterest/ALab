# Codex Worker Prompt: Local Agent Scoreboard

You are inside one ALab experiment worktree for the Local Agent Scoreboard example.

Goal: improve `solution.py`, run one ALab evaluation, and submit only if the run passes.

Rules:
- Edit only `solution.py`.
- Do not edit `.alab/`, ALab home/cache directories, shared run directories, or project control files.
- Do not read secret files, print tokens, or use a root/project admin key.
- Keep the scorer deterministic and easy to review.

Useful checks:

```sh
python solution.py
```

Run evaluation:

```sh
eval "$ALAB_CMD_PREFIX run --message 'local scoreboard worker run'"
```

If the run passes, submit:

```sh
eval "$ALAB_CMD_PREFIX submit --message 'local scoreboard candidate' --summary 'Improved deterministic score.' --feedback 'The latest ALab run passed with a parsed reward.' --ref none"
```

Report the run id, status, reward, and whether submit succeeded.
