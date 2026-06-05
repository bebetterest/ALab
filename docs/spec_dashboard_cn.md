# ALab Root Dashboard 规格

本文档是 [spec_dashboard.md](spec_dashboard.md) 的中文同步版。英文版是规范性来源。本文定义由 `alab dashboard` 启动的 root-only local read-only dashboard。它补充 [spec_cli.md](spec_cli.md) 中的 CLI contract。Dashboard 是本地 operator view，不是 hosted service、remote web UI、sync surface 或 multi-user security boundary。

## 1. 目标和边界

`alab dashboard` 让 root 用户用浏览器只读查看一个已初始化的 ALab home。它应让全局状态更容易检查，但不改变 ALab agent-first CLI workflows。

Dashboard 必须：

- 只绑定 `127.0.0.1`。
- Startup 时要求 valid root key。
- Startup 后只保留 in-memory root actor/session state。
- 生成随机 browser session token，并要求每个 local API call 携带该 token。
- 从现有 SQLite rows 和 file-backed logs、artifacts、feedback records 派生状态。
- 绝不写 audit rows、configuration、caches、records、log/artifact files、tokens 或 feedback。
- 只使用 Python standard library HTTP server；不得新增 FastAPI、Flask、uvicorn 或类似 hosted web frameworks。

Dashboard 可以：

- 通过 `webbrowser.open()` 打开用户浏览器。
- 使用 browser `localStorage`、`sessionStorage` 和 query/filter state 保存 UI preferences。
- 从 `src/alab/dashboard_static/` serve packaged static assets 和 vendored JavaScript/SVG assets。
- 向 root browser session 返回 raw log/artifact bytes，用于 preview 或 download。

## 2. CLI Contract

Invocation：

```text
alab [--home <path>] --key|--key-stdin dashboard [--port <0-65535>] [--no-open] [--refresh-seconds <0-3600>]
```

Defaults：

- Host：`127.0.0.1`。
- Port：`0`，由 OS 选择可用 loopback port。
- Refresh：`15` seconds；`0` 表示关闭 browser 自动轮询，但仍保留 manual refresh。
- Browser open：默认开启，除非提供 `--no-open`。

Startup output：

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

渲染 startup output 后，CLI flush stdout，持续服务直到 interrupted，关闭 server，并在 clean shutdown 时 exit `0`。

## 3. Security Rules

实现使用 `ThreadingHTTPServer` 和受限 handler。Python 的 `http.server` 不是 production server；ALab 通过只绑定 loopback、不提供 directory serving、生成 per-process token，以及发送严格 response headers 来降低风险。

Required HTTP behavior：

- 只接受 `GET` 和 `HEAD`。
- `POST`、`PUT`、`PATCH`、`DELETE` 返回 `405`，且不得 mutate state。
- `/api/*` 要求 `X-ALab-Dashboard-Token`。
- Missing 或 wrong API token 返回 `401`。
- Unknown routes 返回 `404`。
- Sensitive/static dashboard responses 使用 `Cache-Control: no-store`。
- Responses 包含严格 Content Security Policy，只允许 local dashboard origin 的 scripts、styles、images 和 API calls。

Secret handling：

- Raw root/admin keys 和 raw experiment tokens 不得出现在 API responses、static HTML、logs 或 frontend state 中。
- Raw credential verifier hashes 和 salts 不得出现。
- Raw `secret_env` values 不得出现。
- Project config `secret_env` 只能展示 secret names 和 fingerprints。
- Hidden logs 与 full artifact/log bytes 可供 root dashboard session 查看，因为 root CLI authority 已授予该访问能力。

## 4. Routes

Static routes：

- `/`：packaged `index.html`。
- `/static/*`：packaged CSS、JavaScript、Chart.js、Lucide SVG sprite 和 license files。

API routes：

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

除 download responses 外，所有 API output 都是 JSON；download responses 返回 bytes、content type 和 download filename。Project、experiment、run、log、artifact、audit 和 feedback record 的 list routes 接受 `limit` 和 `offset`，最大 `limit` 为 `500`；返回原有 top-level array field，并额外包含 `page` metadata：`limit`、`offset`、`total` 和 `next_offset`。Top-level `projects`、`experiments`、`runs`、`logs`、`artifacts`、`audit` 和 `feedback` list routes 在适用时接受 `query`；`experiments`、`runs`、`logs`、`artifacts` 和 `audit` 接受 `project`；`runs`、`logs` 和 `artifacts` 在适用时接受更窄的 `exp` 或 `run` filters。Project、experiment 和 run detail routes 返回有界 recent related arrays，并附带高容量 related records 的 page totals。API queries 使用 parameterized SQLite queries 和 explicit JSON sanitizers。File reads 必须 resolve 到 ALab-owned project artifact/log storage root 下，并拒绝 path traversal。

## 5. Read Model

Dashboard read model 应暴露：

- Global overview：home health、status distributions、active locks、recent activity、validation health、feedback count、cache/capability/catalog state、artifact/log volume 和 recent failures。
- Projects：sortable/filterable project summaries，包含 status、source count、experiment count、latest activity、run health、artifact/log volume、active config/validation 和 project-local best summary。
- Project detail：overview、有界 recent experiments、runs、sources/config、validations、logs/artifacts、annotations 和 audit records，并带 related-record page totals。Overview 必须包含 project-level aggregate statistics，以及按 project reward direction 绘制 loaded run reward 并连接每个 new best point 的 reward trend chart。
- Run detail：overview、有界 recent logs/artifacts、related-record page totals、parsed metrics、runner/failure metadata、safe log preview/download links，以及 safe artifact preview/download links。
- Experiments：status、tags、source binding、config binding、worktree state、latest/final run、submission 和 reward trend。Free evaluation experiments 会展示 submission 和 final commit，但由于 `final_run_id` 为 `NULL`，没有 final run detail 或 reward trend。
- Runs：status、reward、warnings、runner metadata、stdout/stderr/hidden log references、artifact references、commit/config context 和 failure reasons。
- Logs and artifacts：paginated global/project-scoped metadata lists、chunked full log reads、text/image previews、binary metadata 和 raw downloads。
- Audit、feedback 和 system：searchable audit rows、可搜索且分页的 HOME feedback entries、global config、locks、runtime capabilities、catalogs 和 paginated cache entries。

Reward values 只能在 compatible project/reward-policy context 内比较。Global dashboard 不得展示跨 project leaderboard。

## 6. Frontend Rules

UI 是 packaged static app。它应提供：

- English/Chinese language toggle，并使用 English canonical keys。
- 仅浏览器持久化的 UI preferences，包括 language、selected view、selected project 和 refresh behavior。
- Manual refresh，加 pause/resume auto-refresh。
- Dense tables，带 search、sort、status badges、charts、detail drawers 和 empty/error states。
- 使用 vendored Chart.js 的 responsive charts。
- 无 inline event handlers；scripts 必须保持 CSP-compatible。
- 不提供 edit、delete、archive、revoke、run、submit 或其他 mutation controls。

## 7. Test Requirements

Focused tests 必须覆盖：

- Registry/docs 包含 `dashboard`，object type 为 `dashboard`。
- Root-only capability/preflight；no-key/admin/token/public contexts 不能运行它。
- Invalid `--port` 和 `--refresh-seconds` values 在 server start 前失败。
- Tests 中 `--no-open` 不会打开 browser。
- 所有 `/api/*` routes 拒绝 missing 或 wrong token。
- 非 GET/HEAD methods 返回 `405`，且绝不 mutate state。
- 使用 loopback binding。
- Raw keys、tokens、credential verifier material 和 raw `secret_env` values 不会出现在 API responses。
- Root dashboard sessions 可以访问 hidden log full text。
- Text/image artifact preview 和 binary download 行为安全且 path-contained。
- List routes 返回 bounded pages，并拒绝 invalid pagination values。
- Global assets frontend 使用 top-level paginated `/api/logs` 和 `/api/artifacts` routes，而不是抓取每个 project detail。
- Static frontend assets 避免 inline handlers，并保持 English/Chinese key parity。
