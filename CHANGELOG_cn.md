# 更新日志

ALab 的重要变更记录在这里。每次发布改变用户可见行为时，都要与
`CHANGELOG.md` 保持同步。

## [0.1.2] - 2026-05-30

### 新增

- 新增 `alab report`，用于安全导出 project 和 visible experiment 的 Markdown evidence report。
- 新增有界 dashboard list APIs，以及 top-level log/artifact APIs，以支持更大的本地 home 数据规模。
- 新增 dashboard loaded/total metadata，用于 paginated list 和 detail views。

### 变更

- Version metadata 现在会把 PyPI 用户指向本 changelog。
- Dashboard project、experiment 和 run detail payloads 现在会限制高容量 related rows。

### 修复

- Report best-run selection 现在使用 active valid reward-policy identity，并排除不可比 runs。

