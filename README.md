# Dir Sync

Dir Sync is a cross-platform desktop companion for safe directory backups. It lives in the system tray, lets you define reusable sync actions, watches for removable or network destinations, and surfaces notifications when jobs finish or devices appear.

Think of it as an automated backup / rsync of your important directories.

Setting up directories: 

<img width="1270" height="918" alt="image" src="https://github.com/user-attachments/assets/8e96f02b-0dfa-413a-bf86-a75020a7a59e" />


## Features

- System-tray controller with quick actions (run, add, modify, import/export configuration).
- Configurable source/destination pairs supporting local paths, network drives, and USB devices.
- Safe `backup` actions copy source changes while preserving destination-only files.
- Expert `mirror` actions delete destination-only files to match the source.
- Automation modes: on app start, when the destination device appears, or on cron-style schedules.
- Destination device matching by ID for removable media workflows (USB/HDD reconnect automation).
- Source-change awareness in tray menu labels plus a one-click "Run all changed dirs" action.
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
./start
```
The tray icon appears so you can configure sync pairs or trigger existing jobs.

### Build a Standalone Binary
Use the helper script (which installs PyInstaller if necessary) to mirror the packaging steps from `docs/BUILD.md`:
```bash
./build
```
Artifacts are written to `dist/`.

### Common Commands

Run these commands from the repository root. Each delegates to the existing implementation in `scripts/` and forwards any arguments.

| Command | Purpose |
| --- | --- |
| `./start` | Run the application, building it first when necessary. |
| `./build` | Build the standalone application in `dist/`. |
| `./test` | Run the unit test suite. |
| `./lint` | Run Ruff and Black checks. |
| `./check` | Run linting followed by tests. |
| `./install` / `./uninstall` | Install or remove the local launcher. |
| `./update` | Update the `script-helpers` submodule. |

`Preview only (dry run)` is enabled by default in the tray menu. Leave it checked to inspect changes without copying files, or uncheck it before selecting an action to run it for real.

For additional background or optional packaging targets, see `docs/BUILD.md`. Testing guidance lives in `docs/TESTING.md`.

## Sync profiles

New actions use `backup`: `delete_policy: keep_destination` and `conflict_policy: source_wins`. `mirror` is an expert-only profile with `delete_policy: delete_destination_extras`; the editor requires confirmation before enabling it. Two-way synchronization is unavailable until conflicts can be reconciled safely.

## License

MIT

---

## Clone traffic

![Clone traffic](https://raw.githubusercontent.com/nikolareljin/stats/main/charts/dir-sync.svg)

_Updated daily. Total and unique cloners over the last 14 days._
