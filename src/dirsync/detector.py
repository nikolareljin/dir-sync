from __future__ import annotations

import threading
import time
from typing import Callable, Set

import psutil

from .constants import DRIVE_POLL_SECONDS

DriveHandler = Callable[[str], None]


class DriveDetector:
    def __init__(self, new_drive_handler: DriveHandler, known_drive_handler: DriveHandler):
        self.new_drive_handler = new_drive_handler
        self.known_drive_handler = known_drive_handler
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.known: Set[str] = set()
        self.registered_targets: Set[str] = set()

    def watch_targets(self, targets: Set[str]) -> None:
        self.registered_targets = {t.rstrip("/\\") for t in targets}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():  # pragma: no cover - guard
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop.is_set():
            mounts = self._current_mounts()
            new_mounts = mounts - self.known
            for mount in new_mounts:
                self.new_drive_handler(mount)
                if mount in self.registered_targets:
                    self.known_drive_handler(mount)
            self.known = mounts
            time.sleep(DRIVE_POLL_SECONDS)

    def _current_mounts(self) -> Set[str]:
        mounts = set()
        for part in psutil.disk_partitions(all=False):
            mounts.add(part.mountpoint.rstrip("/\\"))
        return mounts
