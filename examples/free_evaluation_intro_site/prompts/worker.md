# Worker Prompt

You are working inside an ALab experiment worktree for a free evaluation project.
There is no `alab run` command for this project and there is no numeric reward.
The project owner will review the submitted website manually.

Task: complete the Simplified Chinese introduction website for the JTBC drama
`모두가 자신의 무가치함과 싸우고 있다`.

Rules:

- Edit only the source files in the worktree.
- Do not ask for or use a project admin key.
- Do not invent precise facts such as ratings, episode counts, or availability
  unless they are already provided in the source notes or you verify them.
- Keep the page spoiler-safe for new viewers.
- Preserve the static-site shape: `index.html`, `styles.css`, and `script.js`.
- When finished, submit directly with `alab submit`; do not run `alab run`.

Suggested submit shape:

```sh
alab submit \
  --message "complete Chinese intro site" \
  --summary "Completed the Chinese overview, viewing guide, and visual polish for the drama introduction page." \
  --feedback "Free evaluation project: please review index.html in a browser; no automated run was expected." \
  --ref none
```
