# Changelog

## [1.0.0] - 2026-09-18
- Replace ambiguous one-way and two-way methods with explicit backup and mirror profiles.
- Make backup non-destructive and require confirmation before enabling mirror deletes.

## [1.0.0] - 2026-09-18
- Add preflight validation for source and destination paths, schedules, dangerous destinations, destructive configurations, and duplicate action names.
- Validate configuration changes before saving, importing, exporting, or executing actions.
- Use a safe default backup source instead of the entire home directory.

## [0.1.0] - 2024-05-xx
- Scaffold cross-platform Dir Sync app with toolbar, config UI, and notification surfaces.
- Implement YAML-backed sync actions, scheduler, and drive detection hooks.
- Add helper scripts, docs, and CI/CD workflows.
