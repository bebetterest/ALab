# Changelog

All notable ALab changes are recorded here. Keep this file in sync with
`CHANGELOG_cn.md` whenever a release changes user-visible behavior.

## [0.1.2] - 2026-05-31

### Added

- Added `alab report` for safe Markdown project and visible-experiment evidence exports.
- Added bounded dashboard list APIs and top-level log/artifact APIs for large local homes.
- Added dashboard loaded/total metadata for paginated list and detail views.
- Added paginated and searchable dashboard feedback reads.

### Changed

- Version metadata now points PyPI users to this changelog.
- Dashboard project, experiment, and run detail payloads now keep high-volume related rows bounded.
- Observe run, artifact, log, and annotation list paths now execute filtering, whitelisted sorting, null-last ordering, and pagination in SQL for high-volume homes while preserving CLI output contracts.
- Experiment list/search/best paths now push visible filtering, search matching, reward bounds, sorting, pagination, and best-run selection into SQL-backed queries for larger projects.

### Fixed

- Report best-run selection now uses the active valid reward-policy identity and excludes incomparable runs.
- `config validate --refresh-capabilities` now renders actionable `next` remediation for unsupported or error runtime capability checks.
