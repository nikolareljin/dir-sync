# Dir Sync

Dir Sync is a cross-platform desktop companion that keeps directories mirrored through rsync-style actions. It lives in the system toolbar, lets you define reusable sync actions, watches for removable or network destinations, and surfaces notifications when jobs finish or devices appear.

## Features

- System-tray controller with quick actions (run, add, modify, import/export configuration).
- Configurable source/destination pairs supporting local paths, network drives, and USB devices.
- Multiple sync strategies: full two-way reconciliation or one-way source-to-destination mirroring.
- Automation modes: on app start, when the destination device appears, or on cron-style schedules.
- Destination device matching by ID for removable media workflows (USB/HDD reconnect automation).
- Source-change awareness in tray menu labels plus a one-click "Run all changed dirs" action.
- Notification surface for completed jobs, errors, and newly detected drives.
- YAML-based config import/export for sharing actions between machines.

## Getting Started

See `docs/BUILD.md` for environment setup, dependency installation, and packaging guidance. Testing and verification steps are documented in `docs/TESTING.md`.

## License

MIT
