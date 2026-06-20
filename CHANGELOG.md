# Changelog

All notable ALab changes are recorded here. Keep this file in sync with
`CHANGELOG_cn.md` whenever a release changes user-visible behavior.

## [Unreleased]

## [0.1.9] - 2026-06-20

### Added

- Added project reference metric declarations through `metrics.reference`, allowing
  dashboard project run views to plot optional numeric run metrics alongside the
  existing reward trend without changing reward ranking semantics.

## [0.1.8] - 2026-06-07

### Added

- Added a front-of-pipeline CI version synchronization gate that requires
  `pyproject.toml`, `uv.lock`, `src/alab/__init__.py`, `CHANGELOG.md`, and
  `CHANGELOG_cn.md` to agree before lint, tests, or publish jobs run.

### Fixed

- Fixed dashboard reward trend charts so the best-so-far line carries the
  previous best value forward when a later run does not set a new best.
- Fixed dashboard project detail tabs so sticky tabs sit flush against the
  detail header instead of leaving an empty translucent gap while scrolling.
- Fixed dashboard run detail KPI cards so horizontal scrollbars no longer clip
  metric notes or lower card content.

## [0.1.7] - 2026-06-07

### Added

- Added GitHub Release asset uploads for PyPI wheel/sdist files and zipped
  packages for the ALab skill bundle plus the three role skills, after both
  Python and ClawHub publish jobs finish successfully.

## [0.1.6] - 2026-06-07

### Added

- Added `examples/free_evaluation_intro_site`, a no-run free evaluation example
  where workers complete a Chinese static introduction site and submit directly
  for manual review.
- Added push-to-main ClawHub publishing after the Python publish job for the
  ALab skill bundle and three role skill packages, skipping any skill version
  that already exists on ClawHub.

## [0.1.5] - 2026-06-05

### Added

- Added free evaluation projects via `runner.type = "none"` and `reward.type = "none"`, allowing direct experiment submission without evaluator runs, run/log/artifact rows, or best-reward ranking.

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
