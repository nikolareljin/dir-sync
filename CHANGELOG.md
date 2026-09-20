# Changelog

## [1.2.1] - 2026-09-20
- Fix Linux tray menu actions by opening configuration and About windows in a dedicated GUI process.

## [1.2.0] - 2026-09-19
- Add an in-app About dialog and a GitHub Pages documentation site.
- Add safe, synthetic screenshots and detailed guidance for backups, sync modes, and schedules.

## [1.1.0] - 2026-09-19
- Add a guided local-time scheduler and remembered directory browsing.
- Use plain-semver release tags through shared release automation.

## [1.0.0] - 2026-09-18
- Replace ambiguous one-way and two-way methods with explicit backup and mirror profiles.
- Make backup non-destructive and require confirmation before enabling mirror deletes.

## [0.2.0] - 2026-09-18
- Add preflight validation for source and destination paths, schedules, dangerous destinations, destructive configurations, and duplicate action names.
- Validate configuration changes before saving, importing, exporting, or executing actions.
- Use a safe default backup source instead of the entire home directory.

## [0.1.0] - 2024-05-xx
- Scaffold cross-platform Dir Sync app with toolbar, config UI, and notification surfaces.
- Implement YAML-backed sync actions, scheduler, and drive detection hooks.
- Add helper scripts, docs, and CI/CD workflows.
