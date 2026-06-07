# 更新日志

ALab 的重要变更记录在这里。每次发布改变用户可见行为时，都要与
`CHANGELOG.md` 保持同步。

## [Unreleased]

## [0.1.8] - 2026-06-07

### 新增

- 新增 CI 最前置 version synchronization gate：要求 `pyproject.toml`、
  `uv.lock`、`src/alab/__init__.py`、`CHANGELOG.md` 和 `CHANGELOG_cn.md`
  版本一致后，才运行 lint、tests 或 publish jobs。

### 修复

- 修复 dashboard reward trend charts：当后续 run 没有产生新的最佳值时，
  best-so-far 折线会继续沿用此前最佳值。
- 修复 dashboard project detail tabs：滚动时 sticky tabs 会贴住 detail header，
  不再留下半透明空白间隙。
- 修复 dashboard run detail KPI cards：横向滚动条不再裁切 metric notes 或
  卡片下半部分内容。

## [0.1.7] - 2026-06-07

### 新增

- 新增 GitHub Release asset 上传：在 Python 和 ClawHub publish jobs 都成功后，
  上传 PyPI wheel/sdist files，以及 ALab skill bundle 和三个 role skills 的
  zipped packages。

## [0.1.6] - 2026-06-07

### 新增

- 新增 `examples/free_evaluation_intro_site` no-run free evaluation 示例：
  worker 完成中文静态介绍站后直接 submit，由人工 review。
- 新增推送到 `main` 时在 Python publish job 之后执行的 ClawHub 发布：发布
  ALab skill bundle 和三个 role skill packages，并跳过 ClawHub 已存在的
  skill version。

## [0.1.5] - 2026-06-05

### 新增

- 新增 free evaluation projects，可通过 `runner.type = "none"` 和 `reward.type = "none"` 让 experiment 直接 submit，不执行 evaluator run，不产生 run/log/artifact rows，也不参与 best reward ranking。

## [0.1.4] - 2026-06-05

### 新增

- 新增 annotation titles 和 targetless current-experiment annotations，可通过 `alab annotate add --title ...` 创建，并覆盖 title search、可见 experiment evidence/report。

## [0.1.3] - 2026-06-04

### 变更

- 将更多稳定边界的 service object families 从 `src/alab/services.py` 拆出，包括 project lifecycle、project config、project validation、experiment query、experiment lifecycle、experiment access、credential、maintenance、annotation、observe、report、source、catalog、audit、dashboard 和 feedback handlers，同时保持已注册 CLI behavior 不变。
- 通过 lazy exports 集中维护 legacy `alab.services` 对已拆出 handlers 和 helpers 的 compatibility access。

### 修复

- 恢复 legacy `alab.services` 对已拆出的 SkyDiscover catalog constants/helpers 和 registered command handlers 的访问，使 external callers 和 opt-in tests 仍能解析 historical names。

## [0.1.2] - 2026-05-31

### 新增

- 新增 `alab report`，用于安全导出 project 和 visible experiment 的 Markdown evidence report。
- 新增有界 dashboard list APIs，以及 top-level log/artifact APIs，以支持更大的本地 home 数据规模。
- 新增 dashboard loaded/total metadata，用于 paginated list 和 detail views。
- 新增 paginated/searchable dashboard feedback reads。
- 新增 root-only `feedback list`、`feedback show` 和幂等 `feedback archive` commands，用于 file-backed HOME feedback records。

### 变更

- Version metadata 现在会把 PyPI 用户指向本 changelog。
- Feedback file metadata 现在记录 active/archived status，同时保留既有 public submit command 和 plaintext file-backed storage model。
- Dashboard project、experiment 和 run detail payloads 现在会限制高容量 related rows。
- Observe run、artifact、log 和 annotation list paths 现在会在 SQL 中执行 filtering、whitelisted sorting、null-last ordering 和 pagination，以支持高容量 home，同时保持 CLI output contracts 不变。
- Experiment list/search/best paths 现在会把 visible filtering、search matching、reward bounds、sorting、pagination 和 best-run selection 下推到 SQL-backed queries，以支持更大的 projects。

### 修复

- Report best-run selection 现在使用 active valid reward-policy identity，并排除不可比 runs。
- `config validate --refresh-capabilities` 现在会为 unsupported 或 error runtime capability checks 渲染可操作的 `next` remediation。
