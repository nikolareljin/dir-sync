"""Entry script for PyInstaller builds.

PyInstaller expects a concrete file to analyze. The primary application lives in
``dirsync.app`` and relies on package-relative imports, so executing the module
directly via ``python -m dirsync.app`` works but running the file path does not.
This shim imports the canonical entrypoint so PyInstaller can resolve
dependencies correctly.
"""

from dirsync.app import main


if __name__ == "__main__":  # pragma: no cover - used only during packaging
  main()
