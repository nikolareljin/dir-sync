# Packaging

This folder contains cross-distribution packaging metadata and helper files.

## Layout

- `../debian/` - Debian packaging (dpkg-buildpackage, Launchpad PPA).
- `rpm/` - RPM spec and build output.
- `arch/` - PKGBUILD for Arch Linux.
- `brew/` - Homebrew formula template.
- `packaging.env` - shared metadata values used by templates.

## Build commands

From the repo root:

- Debian: `make deb`
- RPM: `make rpm`
- Arch: `bash ./scripts/script-helpers/scripts/build_arch_artifacts.sh --repo .`

## Homebrew

Render a formula with the current version and a SHA256:

```
make brew
```

## Notes

- Edit `packaging.env` first; rerun `make package-refresh` to regenerate files.
- For PPA uploads, use `make ppa-dry-run` / `make ppa` and provide Launchpad key info.
