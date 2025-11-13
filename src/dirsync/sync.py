from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

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
            self._run_one_way(action.src_path, action.dst_path, action)
        self.notifier.success(f"Action '{action.name}' completed")

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
