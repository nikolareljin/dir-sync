# Build & Packaging

## Prerequisites
- Python 3.10+
- `pipx` or `pip` for installing project dependencies
- `rsync` available on Linux/macOS; for Windows install cwRsync or enable WSL
- Optional: `pyinstaller` for producing standalone executables

## Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install --upgrade pip
pip install -e .[dev]
```

## Running the App Locally
```bash
python -m dirsync.app
```
The toolbar icon appears in your system tray. Use the menu to add sync actions, run jobs, or import/export YAML configs.

## Packaging
```bash
pip install pyinstaller
pyinstaller --name dir-sync --onefile --windowed src/dirsync/app.py
```
Artifacts land in `dist/`. Repeat on Linux/macOS/Windows to create native binaries (GitHub Actions workflows do this automatically when tags are pushed).
