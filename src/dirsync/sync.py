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

    def run_action(self, action: SyncAction, soft_run: bool = False) -> None:
        outputs: list[str] = []
        if action.method == "two_way":
            outputs.append(
                self._run_one_way(action.src_path, action.dst_path, action, soft_run=soft_run)
            )
            outputs.append(
                self._run_one_way(
                    action.dst_path, action.src_path, action, reverse=True, soft_run=soft_run
                )
            )
        else:
            outputs.append(self._run_one_way(action.src_path, action.dst_path, action, soft_run))
        if soft_run:
            combined = "\n".join([o for o in outputs if o]).strip()
            message = combined if combined else f"Preview for '{action.name}' completed"
            self.notifier.prompt("Dir Sync preview", message[:500])
        else:
            self.notifier.success(f"Action '{action.name}' completed")

    def _run_one_way(
        self, src: str, dst: str, action: SyncAction, reverse: bool = False, soft_run: bool = False
    ) -> str:
        src_path = Path(src)
        dst_path = Path(dst)
        if not soft_run:
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
            if soft_run:
                cmd.insert(1, "--dry-run")
                cmd.insert(2, "--stats")
            return self._run_command(cmd, label, soft_run)
        elif self.robocopy_path:
            cmd = [
                "robocopy",
                str(src_path),
                str(dst_path),
                "/MIR",
            ]
            if soft_run:
                cmd.append("/L")
            return self._run_command(cmd, label, soft_run)
        else:
            if soft_run:
                return "Soft run not available without rsync/robocopy; install rsync to preview."
            self.logger.warning("rsync not available; falling back to shutil copy")
            self._python_copy(src_path, dst_path)
            return ""

    def _run_command(self, cmd: Iterable[str], label: str, soft_run: bool = False) -> str:
        self.logger.info("Running %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.logger.error("Sync command failed: %s", result.stderr)
            self.notifier.error(f"{label} failed: {result.stderr.strip()[:200]}")
            alert(f"Sync failed for {label}: {result.stderr}")
            raise RuntimeError(result.stderr)
        if soft_run:
            preview = result.stdout.strip() or f"{label} dry run completed"
            return preview
        return ""

    def _python_copy(self, src: Path, dst: Path) -> None:
        for item in src.rglob("*"):
            target = dst / item.relative_to(src)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
