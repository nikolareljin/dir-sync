# Testing & Validation

## Lint & Unit Tests
```bash
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pytest --maxfail=1 --disable-warnings -q
ruff check src tests
```

Or run the tests in Docker without touching your host environment:
```bash
./scripts/test_in_docker.sh
```

## End-to-End Smoke
1. Start the app: `python -m dirsync.app`.
2. Add a manual action via the toolbar and run it.
3. Plug a USB drive (or mount a network share) and confirm that notifications prompt you to sync or create an automation.

## CI
GitHub Actions run lint, tests, and packaging on pull requests. Tagged releases trigger cross-platform builds (`dist/dir-sync-<os>.zip`) so you can download ready-to-run binaries.
