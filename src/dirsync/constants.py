from __future__ import annotations

import platform
from pathlib import Path

APP_NAME = "Dir Sync"
CONFIG_DIR = Path.home() / ".config" / "dir-sync"
CONFIG_PATH = Path(CONFIG_DIR) / "config.yml"
EXPORT_DIR = Path.home() / "dir-sync-exports"
SUPPORTED_METHODS = ("two_way", "one_way")
SUPPORTED_ACTION_TYPES = (
    "manual",
    "auto_on_start",
    "auto_on_destination",
    "scheduled",
)
DRIVE_POLL_SECONDS = 10

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
