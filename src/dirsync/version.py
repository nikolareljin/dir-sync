from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_app_version() -> str:
    """Return the installed package version, including in packaged builds."""
    try:
        return version("dir-sync")
    except PackageNotFoundError:
        return "development build"
