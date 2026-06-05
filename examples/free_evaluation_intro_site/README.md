# Free Evaluation Intro Site Example

This example demonstrates ALab free evaluation mode with an open-ended static
website task. The project has `runner.type = "none"` and `reward.type = "none"`,
so experiments submit directly and a human project owner reviews the final
commit instead of reading a numeric reward.

## Demo Task

Complete `source/index.html`, `source/styles.css`, and `source/script.js` into a
Simplified Chinese introduction website for the JTBC drama
`모두가 자신의 무가치함과 싸우고 있다`.

Task shape:

- Editable files: `index.html`, `styles.css`, `script.js`, and
  `content-notes.md`.
- Baseline behavior: a working but unfinished static page with TODO-style copy.
- Demo improvement: `scripts/run_demo.sh` creates one experiment, replaces the
  starter with a more complete Chinese page, and submits without running an
  evaluator.
- Review source: the submitted commit, summary, and feedback.
- Reward source: none. The project is intentionally manual-review only.

Use this example when a task depends on taste, writing quality, factual care,
or product judgment rather than a repeatable local score.

## What It Covers

- free evaluation project config;
- `not_required` validation status during project init;
- direct `alab submit` without `alab run`;
- nullable `final run id` rendered as `none`;
- manual review workflow for design and writing tasks.

## Run

From the repository root:

```sh
examples/free_evaluation_intro_site/scripts/setup_project.sh --dry-run
examples/free_evaluation_intro_site/scripts/setup_project.sh
examples/free_evaluation_intro_site/scripts/run_demo.sh
```

Generated state stays under ignored `.run/`. The project admin key is stored
only in `.run/secrets/project.env`; workers do not need it for public experiment
creation or token-scoped submission.

## Inspect The Result

After `scripts/run_demo.sh`, open the submitted worktree's `index.html` directly
in a browser. The script also writes a compact report to:

```text
examples/free_evaluation_intro_site/.run/reports/report.md
```

Free evaluation does not create run, log, artifact, or reward rows. Review the
experiment submission and final commit instead.
