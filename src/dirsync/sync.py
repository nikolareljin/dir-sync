from __future__ import annotations

import logging
import os
import shutil
import subprocess
from hashlib import sha1
from pathlib import Path
from typing import Iterable, Sequence

from .config import SyncAction
from .constants import IS_WINDOWS
from .notifications import Notifier
from .ui_dialogs import alert


class SyncExecutor:
    def __init__(self, notifier: Notifier):
        self.logger = logging.getLogger(__name__)
        self.notifier = notifier
        self.rsync_path = shutil.which("rsync")
        self.robocopy_path = shutil.which("robocopy") if IS_WINDOWS else None

    def run_action(self, action: SyncAction) -> None:
        if action.method == "two_way":
            self._run_one_way(action.src_path, action.dst_path, action)
            self._run_one_way(action.dst_path, action.src_path, action, reverse=True)
        else:
            self.run_source_to_destination(action)
        self.notifier.success(f"Action '{action.name}' completed")

    def run_source_to_destination(self, action: SyncAction) -> None:
        self._run_one_way(action.src_path, action.dst_path, action)

    def _run_one_way(self, src: str, dst: str, action: SyncAction, reverse: bool = False) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        dst_path.mkdir(parents=True, exist_ok=True)
        label = f"{action.name} ({'dst→src' if reverse else 'src→dst'})"
        if self.rsync_path:
            cmd = [
                self.rsync_path,
                "-avh",
                "--delete",
                f"{src_path}/",
                f"{dst_path}/",
            ]
            self._run_command(cmd, label)
        elif self.robocopy_path:
            cmd = [
                "robocopy",
                str(src_path),
                str(dst_path),
                "/MIR",
            ]
            self._run_command(cmd, label)
        else:
            self.logger.warning("rsync not available; falling back to shutil copy")
            self._python_copy(src_path, dst_path)

    def _run_command(self, cmd: Iterable[str], label: str) -> None:
        self.logger.info("Running %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.logger.error("Sync command failed: %s", result.stderr)
            self.notifier.error(f"{label} failed: {result.stderr.strip()[:200]}")
            alert(f"Sync failed for {label}: {result.stderr}")
            raise RuntimeError(result.stderr)

    def _python_copy(self, src: Path, dst: Path) -> None:
        for item in src.rglob("*"):
            target = dst / item.relative_to(src)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    def has_pending_source_changes(self, action: SyncAction) -> bool:
        src = Path(action.src_path)
        dst = Path(action.dst_path)
        if not src.exists():
            return False
        if not dst.exists():
            return True
        if self.rsync_path:
            return self._rsync_has_pending(src, dst)
        return self._fallback_has_pending(src, dst)

    def pending_actions(self, actions: Sequence[SyncAction]) -> list[SyncAction]:
        return [action for action in actions if self.has_pending_source_changes(action)]

    def _rsync_has_pending(self, src: Path, dst: Path) -> bool:
        cmd = [self.rsync_path, "-ani", "--delete", f"{src}/", f"{dst}/"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.logger.warning("Could not evaluate pending changes: %s", result.stderr.strip())
            return True
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return bool(lines)

    def _fallback_has_pending(self, src: Path, dst: Path) -> bool:
        src_files = self._snapshot(src)
        dst_files = self._snapshot(dst)
        if set(src_files.keys()) != set(dst_files.keys()):
            return True
        for key, src_meta in src_files.items():
            if src_meta != dst_files.get(key):
                return True
        return False

    def _snapshot(self, root: Path) -> dict[str, tuple[int, int, str]]:
        snapshot: dict[str, tuple[int, int, str]] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = os.fspath(path.relative_to(root))
            stat = path.stat()
            snapshot[rel] = (stat.st_size, stat.st_mtime_ns, self._file_hash(path))
        return snapshot

    def _file_hash(self, path: Path) -> str:
        digest = sha1()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
