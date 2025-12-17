from __future__ import annotations

from pathlib import Path
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
        self.registered_targets = {self._normalize(t) for t in targets}

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
                if self._has_registered_target_on_mount(mount):
                    self.known_drive_handler(mount)
            self.known = mounts
            time.sleep(DRIVE_POLL_SECONDS)

    def _current_mounts(self) -> Set[str]:
        mounts: Set[str] = set()
        for part in psutil.disk_partitions(all=True):
            if not part.mountpoint:
                continue
            if self._is_pseudo_mount(part):
                continue
            mounts.add(self._normalize(part.mountpoint))
        return mounts

    def _is_pseudo_mount(self, part: psutil._common.sdiskpart) -> bool:
        fstype = (part.fstype or "").lower()
        mount = part.mountpoint

        skip_mounts = {
            "/boot",
            "/boot/efi",
            "/home",
        }
        skip_types = {
            "proc",
            "sysfs",
            "tmpfs",
            "devtmpfs",
            "devfs",
            "overlay",
            "autofs",
            "squashfs",
            "fusectl",
            "debugfs",
            "tracefs",
            "securityfs",
            "cgroup",
            "cgroup2",
            "binfmt_misc",
            "pstore",
            "efivarfs",
            "mqueue",
            "devpts",
            "rpc_pipefs",
            "nsfs",
            "portal",
        }
        allowed_fuse = {"fuseblk", "fuse.ntfs", "fuse.sshfs"}

        normalized_mount = str(Path(mount).resolve()).rstrip("/\\")

        if normalized_mount in skip_mounts:
            return True
        if fstype in skip_types:
            return True
        if fstype.startswith("fuse.") and fstype not in allowed_fuse:
            return True

        skip_prefixes = (
            "/snap/",
            "/proc/",
            "/sys/",
            "/dev/",
            "/run/snapd/",
            "/run/docker/netns/",
            "/run/user/",
            "/var/snap/",
        )
        if any(mount.startswith(prefix) for prefix in skip_prefixes):
            return True
        # Avoid pseudo user portals like xdg-doc portal (under /run/user/*/doc)
        if "/doc" in mount and "run/user" in mount:
            return True
        return False

    def _has_registered_target_on_mount(self, mount: str) -> bool:
        for target in self.registered_targets:
            if self._is_target_on_mount(target, mount):
                return True
        return False

    def _is_target_on_mount(self, target: str, mount: str) -> bool:
        norm_mount = self._normalize(mount)
        norm_target = self._normalize(target)
        try:
            mount_path = Path(norm_mount)
            target_path = Path(norm_target)
            return target_path == mount_path or target_path.is_relative_to(mount_path)
        except Exception:
            return norm_target.startswith(norm_mount)

    def _normalize(self, value: str) -> str:
        try:
            normalized = str(Path(value).resolve())
        except Exception:
            normalized = value
        return normalized.rstrip("/\\")
