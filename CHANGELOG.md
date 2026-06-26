# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-26

### Added

- `show_chunks` and `drop_chunks` helpers for inspecting and removing
  hypertable chunks.
- Background job helpers for listing jobs, inspecting job stats, running jobs,
  altering schedules, and deleting jobs.
- README documentation for chunk management and background jobs.
- Integration and SQL-builder tests for the new chunk and job APIs.

### Changed

- Bumped the package to the `0.1.x` release line.

### Fixed

- Rejected integer bounds for chunk `created_before` / `created_after` filters,
  which only accept timestamp or interval values.

## [0.0.7] - 2026-06-25

Production-readiness hardening release.

### Added

- SQLAlchemy dialect support, including psycopg 3.
- `py.typed` marker so downstream consumers pick up the package's type hints.
- `LICENSE` and `CONTRIBUTING.md` files.
- mypy type checking and flake8 linting jobs in CI.
- Python 3.14 to the CI test matrix.
- `get_defaults()` helper to inspect the package's default settings.
- Database-free unit tests for the engine and query builders.

### Changed

- Moved `fastapi` and `uvicorn` out of the core dependencies into optional extras.
- Bumped GitHub Actions off the deprecated Node 20 runtime and added job timeouts.
- Pinned `setup-uv` to a fixed version.
- Cleaned up the requirements compile script (dropped a vestigial `--constraint -`).
- Coverage now fails the build below 85% instead of merely warning.

### Fixed

- Repaired broken `__all__` exports.
- Hardened sync error handling so failures roll back the session and propagate
  instead of being silently swallowed.

## [0.0.6] - 2026-06-25

### Changed

- Version bump release (0.0.5 → 0.0.6).

## [0.0.5] - 2026-06-25

### Added

- Hypercore columnstore support.
- Continuous aggregate support.
- `samples/`: 10 runnable, Docker-tested TimescaleDB sample projects.

## [0.0.4] - 2025-03-20

### Changed

- Reworked retention handling.
- Dropped Python 3.10 support.

### Fixed

- Updated and expanded the test suite.

## [0.0.3] - 2025-03-20

### Added

- Compression policies.

### Changed

- Updates to hypertable creation, compression, and retention.
- Reorganized the codebase into focused modules.
- Improved test coverage and updated the README example.

## [0.0.2] - 2025-02-19

### Changed

- Updated dependencies.
- Updated the sample project.

## [0.0.1] - 2025-02-17

### Added

- Initial release: the TimescaleDB model and base package layout.
