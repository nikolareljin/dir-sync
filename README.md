# Dir Sync

Dir Sync is a cross-platform desktop companion that keeps directories mirrored through rsync-style actions. It lives in the system tray, lets you define reusable sync actions, watches for removable or network destinations, and surfaces notifications when jobs finish or devices appear.

## Features

- System-tray controller with quick actions (run, add, modify, import/export configuration).
- Configurable source/destination pairs supporting local paths, network drives, and USB devices.
- Multiple sync strategies: full two-way reconciliation or one-way source-to-destination mirroring.
- Automation modes: on app start, when the destination device appears, or on cron-style schedules.
- Notification surface for completed jobs, errors, and newly detected drives.
- YAML-based config import/export for sharing actions between machines.

## Getting Started

### Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e .[dev]
```

### Run the App
```bash
python -m dirsync.app
```
The tray icon appears so you can configure sync pairs or trigger existing jobs.

### Build a Standalone Binary
Use the helper script (which installs PyInstaller if necessary) to mirror the packaging steps from `docs/BUILD.md`:
```bash
./scripts/build.sh
```
Artifacts are written to `dist/`.

For additional background or optional packaging targets, see `docs/BUILD.md`. Testing guidance lives in `docs/TESTING.md`.

## License

MIT
