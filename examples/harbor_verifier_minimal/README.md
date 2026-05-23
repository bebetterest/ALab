# Harbor Verifier Minimal Example

This example demonstrates ALab's Harbor adapter with a hidden verifier task.
Only `starter/main.py` becomes editable source; `tests/`, verifier logic, and
task-private files stay hidden from workers and token-visible artifacts.

## Demo Task

The editable candidate implements an incident-ticket urgency classifier with
`score_ticket(text)` and `classify_ticket(text)`. The hidden verifier imports
those functions and scores private SLA cases such as outage, breach, login, and
cosmetic documentation tickets.

The baseline misses several high-impact phrases. `scripts/run_demo.sh` edits
the worktree candidate to recognize breach, login, and customer-impact signals,
then runs the Harbor verifier and lists hidden-capable logs with the project
admin key.

Task shape:

- Editable file: `task/starter/main.py`, imported into the experiment worktree
  as `main.py`.
- Public contract: keep `score_ticket(text)` and `classify_ticket(text)`.
- Hidden verifier: `task/tests/test.sh` imports the candidate and scores private
  cases. Workers do not receive the verifier as editable source.
- Baseline behavior: recognizes obvious outage/data-loss wording but misses
  breach, login, and customer-impact language.
- Demo improvement: adds those high-impact signals and lowers the urgency
  threshold for the private SLA cases.
- Reward source: Harbor reads `logs/verifier/reward.json`; it must contain only
  finite numeric metrics. Detailed case diagnostics are written as hidden
  verifier log content instead.

This example is useful for demonstrating why verifier assets and hidden logs
must stay outside worker access. The worker can improve the public interface
without seeing the private test cases.

## Requirements

- Docker daemon and access to `python:3.11-alpine`.

## Run

```sh
examples/harbor_verifier_minimal/scripts/setup_project.sh --dry-run
examples/harbor_verifier_minimal/scripts/setup_project.sh
examples/harbor_verifier_minimal/scripts/run_demo.sh
```

## What It Covers

- Harbor `source = "starter"` editable-source import;
- private verifier execution in Docker;
- Harbor reward parsing from `logs/verifier/reward.json`;
- hidden verifier logs visible only with admin/root `--include-hidden`.
