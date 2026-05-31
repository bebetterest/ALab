# ALab Root Dashboard Spec

This spec defines the root-only local read-only dashboard launched by `alab dashboard`. It complements the CLI contract in [spec_cli.md](spec_cli.md). The dashboard is a local operator view, not a hosted service, remote web UI, sync surface, or multi-user security boundary.

## 1. Goals And Boundaries

`alab dashboard` gives a root user a browser-based read-only view of an initialized ALab home. It should make global state easier to inspect without changing ALab's agent-first CLI workflows.

The dashboard must:

- Bind only to `127.0.0.1`.
- Require a valid root key at startup.
- Keep only in-memory root actor/session state after startup.
- Generate a random browser session token and require it for every local API call.
- Derive state from existing SQLite rows and file-backed logs, artifacts, and feedback records.
- Never write audit rows, configuration, caches, records, log/artifact files, tokens, or feedback.
- Use the Python standard library HTTP server only; do not add FastAPI, Flask, uvicorn, or similar hosted web frameworks.

The dashboard may:

- Open the user's browser through `webbrowser.open()`.
- Use browser `localStorage`, `sessionStorage`, and query/filter state for UI preferences.
- Serve packaged static assets and vendored JavaScript/SVG assets from `src/alab/dashboard_static/`.
- Return raw log/artifact bytes to the root browser session for preview or download.

## 2. CLI Contract

Invocation:

```text
alab [--home <path>] --key|--key-stdin dashboard [--port <0-65535>] [--no-open] [--refresh-seconds <0-3600>]
```

Defaults:

- Host: `127.0.0.1`.
- Port: `0`, letting the OS choose a free loopback port.
- Refresh: `15` seconds; `0` disables automatic browser polling while keeping manual refresh available.
- Browser open: enabled unless `--no-open` is provided.

Startup output:

```text
object: dashboard
url: http://127.0.0.1:<port>/#token=<session-token>
host: 127.0.0.1
port: <port>
refresh seconds: <seconds>
opened: true|false
auth scope: root
next: press Ctrl-C to stop the local read-only dashboard
```

After rendering startup output the CLI flushes stdout, serves until interrupted, closes the server, and exits `0` on clean shutdown.

## 3. Security Rules

The implementation uses `ThreadingHTTPServer` with a constrained handler. Python's `http.server` is not a production server; ALab mitigates that by binding only to loopback, serving no directories, generating a per-process token, and sending restrictive response headers.

Required HTTP behavior:

- `GET` and `HEAD` are the only accepted methods.
- `POST`, `PUT`, `PATCH`, and `DELETE` return `405` and must not mutate state.
- `/api/*` requires `X-ALab-Dashboard-Token`.
- Missing or wrong API token returns `401`.
- Unknown routes return `404`.
- Sensitive/static dashboard responses use `Cache-Control: no-store`.
- Responses include a restrictive Content Security Policy that allows scripts, styles, images, and API calls only from the local dashboard origin.

Secret handling:

- Raw root/admin keys and raw experiment tokens must never appear in API responses, static HTML, logs, or frontend state.
- Raw credential verifier hashes and salts must never appear.
- Raw `secret_env` values must never appear.
- Project config `secret_env` may expose secret names and fingerprints only.
- Hidden logs and full artifact/log bytes are available to the root dashboard session because root CLI authority already grants that access.

## 4. Routes

Static routes:

- `/`: packaged `index.html`.
- `/static/*`: packaged CSS, JavaScript, Chart.js, Lucide SVG sprite, and license files.

API routes:

- `/api/summary`
- `/api/projects`
- `/api/projects/{id}`
- `/api/experiments`
- `/api/experiments/{id}`
- `/api/runs`
- `/api/runs/{id}`
- `/api/logs`
- `/api/logs/{id}/content`
- `/api/logs/{id}/download`
- `/api/artifacts`
- `/api/artifacts/{id}/preview`
- `/api/artifacts/{id}/download`
- `/api/audit`
- `/api/feedback`
- `/api/system`

All API output is JSON except download responses, which return bytes with content type and download filename. List routes for project, experiment, run, log, artifact, audit, and feedback records accept `limit` and `offset` with a maximum `limit` of `500`, return the same top-level array field as before, and include `page` metadata with `limit`, `offset`, `total`, and `next_offset`. Top-level `projects`, `experiments`, `runs`, `logs`, `artifacts`, `audit`, and `feedback` list routes accept `query` where applicable; `experiments`, `runs`, `logs`, `artifacts`, and `audit` accept `project`; `runs`, `logs`, and `artifacts` accept narrower `exp` or `run` filters where applicable. Project, experiment, and run detail routes return bounded recent related arrays plus page totals for high-volume related records. API queries use parameterized SQLite queries and explicit JSON sanitizers. File reads must resolve under the ALab-owned project artifact/log storage root and reject path traversal.

## 5. Read Model

The dashboard read model should expose:

- Global overview: home health, status distributions, active locks, recent activity, validation health, feedback count, cache/capability/catalog state, artifact/log volume, and recent failures.
- Projects: sortable/filterable project summaries with status, source count, experiment count, latest activity, run health, artifact/log volume, active config/validation, and project-local best summary.
- Project detail: overview, bounded recent experiments, runs, sources/config, validations, logs/artifacts, annotations, and audit records with related-record page totals. Overview must include project-level aggregate statistics and a reward trend chart that plots each loaded run reward and connects each new best point according to the project's reward direction.
- Run detail: overview, bounded recent logs/artifacts, related-record page totals, parsed metrics, runner/failure metadata, safe log preview/download links, and safe artifact preview/download links.
- Experiments: status, tags, source binding, config binding, worktree state, latest/final run, submission, and reward trend.
- Runs: status, reward, warnings, runner metadata, stdout/stderr/hidden log references, artifact references, commit/config context, and failure reasons.
- Logs and artifacts: paginated global/project-scoped metadata lists, chunked full log reads, text/image previews, binary metadata, and raw downloads.
- Audit, feedback, and system: searchable audit rows, searchable and paginated HOME feedback entries, global config, locks, runtime capabilities, catalogs, and paginated cache entries.

Reward values should be compared only within compatible project/reward-policy context. The global dashboard must not present a cross-project leaderboard.

## 6. Frontend Rules

The UI is a packaged static app. It should provide:

- English and Chinese language toggle with English canonical keys.
- Persistent browser-only UI preferences for language, selected view, selected project, and refresh behavior.
- Manual refresh plus pause/resume auto-refresh.
- Dense tables with search, sort, status badges, charts, detail drawers, and empty/error states.
- Responsive Chart.js charts using vendored Chart.js.
- No inline event handlers; scripts must remain CSP-compatible.
- No edit, delete, archive, revoke, run, submit, or other mutation controls.

## 7. Test Requirements

Focused tests must cover:

- Registry/docs include `dashboard` with object type `dashboard`.
- Root-only capability/preflight; no-key/admin/token/public contexts cannot run it.
- Invalid `--port` and `--refresh-seconds` values fail before server start.
- `--no-open` avoids browser launch in tests.
- All `/api/*` routes reject missing or wrong tokens.
- Non-GET/HEAD methods return `405` and never mutate state.
- Loopback binding is used.
- Raw keys, tokens, credential verifier material, and raw `secret_env` values do not appear in API responses.
- Hidden log full-text access works for root dashboard sessions.
- Text/image artifact preview and binary download behavior are safe and path-contained.
- List routes return bounded pages and reject invalid pagination values.
- The global assets frontend uses top-level paginated `/api/logs` and `/api/artifacts` routes instead of fetching every project detail.
- Static frontend assets avoid inline handlers and keep English/Chinese key parity.
