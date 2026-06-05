# Changelog

All notable ALab changes are recorded here. Keep this file in sync with
`CHANGELOG_cn.md` whenever a release changes user-visible behavior.

## [Unreleased]

## [0.1.4] - 2026-06-05

### Added

- Added annotation titles and targetless current-experiment annotations with `alab annotate add --title ...`, including title search and visible experiment evidence/report coverage.

## [0.1.3] - 2026-06-04

### Changed

- Split additional stable service object families out of `src/alab/services.py`, including project lifecycle, project config, project validation, experiment query, experiment lifecycle, experiment access, credential, maintenance, annotation, observe, report, source, catalog, audit, dashboard, and feedback handlers, while preserving registered CLI behavior.
- Centralized legacy `alab.services` compatibility access for extracted handlers and helpers through lazy exports.

### Fixed

- Restored legacy `alab.services` access for extracted SkyDiscover catalog constants/helpers and registered command handlers so external callers and opt-in tests can continue resolving historical names.

## [0.1.2] - 2026-05-31

### Added

- Added `alab report` for safe Markdown project and visible-experiment evidence exports.
- Added bounded dashboard list APIs and top-level log/artifact APIs for large local homes.
- Added dashboard loaded/total metadata for paginated list and detail views.
- Added paginated and searchable dashboard feedback reads.
- Added root-only `feedback list`, `feedback show`, and idempotent `feedback archive` commands for file-backed HOME feedback records.

### Changed

- Version metadata now points PyPI users to this changelog.
- Feedback file metadata now records active/archived status while preserving the existing public submit command and plaintext file-backed storage model.
- Dashboard project, experiment, and run detail payloads now keep high-volume related rows bounded.
- Observe run, artifact, log, and annotation list paths now execute filtering, whitelisted sorting, null-last ordering, and pagination in SQL for high-volume homes while preserving CLI output contracts.
- Experiment list/search/best paths now push visible filtering, search matching, reward bounds, sorting, pagination, and best-run selection into SQL-backed queries for larger projects.

### Fixed

- Report best-run selection now uses the active valid reward-policy identity and excludes incomparable runs.
- `config validate --refresh-capabilities` now renders actionable `next` remediation for unsupported or error runtime capability checks.
