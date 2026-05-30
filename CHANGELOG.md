# Changelog

All notable ALab changes are recorded here. Keep this file in sync with
`CHANGELOG_cn.md` whenever a release changes user-visible behavior.

## [0.1.2] - 2026-05-30

### Added

- Added `alab report` for safe Markdown project and visible-experiment evidence exports.
- Added bounded dashboard list APIs and top-level log/artifact APIs for large local homes.
- Added dashboard loaded/total metadata for paginated list and detail views.

### Changed

- Version metadata now points PyPI users to this changelog.
- Dashboard project, experiment, and run detail payloads now keep high-volume related rows bounded.

### Fixed

- Report best-run selection now uses the active valid reward-policy identity and excludes incomparable runs.

