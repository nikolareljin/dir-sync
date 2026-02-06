from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Set

import psutil

from .constants import DRIVE_POLL_SECONDS


@dataclass(frozen=True)
class MountedDrive:
    mountpoint: str
    device: str
    volume_id: str
    is_removable: bool


DriveHandler = Callable[[MountedDrive], None]


class DriveDetector:
    def __init__(self, new_drive_handler: DriveHandler, known_drive_handler: DriveHandler):
        self.new_drive_handler = new_drive_handler
        self.known_drive_handler = known_drive_handler
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.known: dict[str, MountedDrive] = {}
        self.registered_targets: Set[str] = set()
        self.registered_device_ids: Set[str] = set()
        self._uuid_cache: dict[str, str] = {}

    def watch_targets(self, targets: Set[str], device_ids: Set[str] | None = None) -> None:
        self.registered_targets = {t.rstrip("/\\") for t in targets}
        self.registered_device_ids = {
            value.strip() for value in (device_ids or set()) if value.strip()
        }

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
            new_mount_points = set(mounts) - set(self.known)
            for mount in new_mount_points:
                drive = mounts[mount]
                self.new_drive_handler(drive)
                if (
                    drive.mountpoint in self.registered_targets
                    or drive.volume_id in self.registered_device_ids
                ):
                    self.known_drive_handler(drive)
            self.known = mounts
            time.sleep(DRIVE_POLL_SECONDS)

    def _current_mounts(self) -> dict[str, MountedDrive]:
        mounts: dict[str, MountedDrive] = {}
        for part in psutil.disk_partitions(all=False):
            mountpoint = part.mountpoint.rstrip("/\\")
            device = part.device
            mounts[mountpoint] = MountedDrive(
                mountpoint=mountpoint,
                device=device,
                volume_id=self._resolve_volume_id(device),
                is_removable=self._is_removable(device),
            )
        return mounts

    def _resolve_volume_id(self, device: str) -> str:
        if not device:
            return ""
        if device in self._uuid_cache:
            return self._uuid_cache[device]

        by_uuid = Path("/dev/disk/by-uuid")
        resolved = Path(device).resolve()
        if by_uuid.exists():
            for entry in by_uuid.iterdir():
                try:
                    if entry.resolve() == resolved:
                        self._uuid_cache[device] = entry.name
                        return entry.name
                except OSError:
                    continue

        self._uuid_cache[device] = device
        return device

    def _is_removable(self, device: str) -> bool:
        if not device.startswith("/dev/"):
            return False

        leaf = Path(device).name
        candidates = [leaf]
        if leaf and leaf[-1].isdigit():
            candidates.append(leaf.rstrip("0123456789"))
            candidates.append(leaf.rstrip("0123456789p"))

        for name in candidates:
            sys_path = Path("/sys/class/block") / name / "removable"
            if not sys_path.exists():
                continue
            try:
                return sys_path.read_text(encoding="utf-8").strip() == "1"
            except OSError:
                return False
        return False
