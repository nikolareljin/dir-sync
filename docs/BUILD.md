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
make build
```
Artifacts land in `dist/`.

## Cross-Distro Packaging
The repo includes packaging metadata plus helper targets for Debian, Launchpad PPA, RPM, and Homebrew.

```bash
# one-time scaffold refresh from packaging/packaging.env
make package-refresh

# build package artifacts
make deb
make rpm
make brew
```

PPA upload requires your Launchpad target and signing key:

```bash
make ppa-dry-run PPA=ppa:<owner>/<name> PPA_KEY_ID=<gpg-key-id>
make ppa PPA=ppa:<owner>/<name> PPA_KEY_ID=<gpg-key-id>
```

Homebrew tap publishing:

```bash
make brew-publish BREW_TAP_REPO=<owner>/<homebrew-tap-repo>
```
