from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import subprocess
from hashlib import sha1
from pathlib import Path
from typing import Iterable, List, Sequence

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
            outputs.append(
                self._run_one_way(action.src_path, action.dst_path, action, soft_run=soft_run)
            )

        if soft_run:
            combined = "\n".join([o for o in outputs if o]).strip()
            message = combined if combined else f"Preview for '{action.name}' completed"
            self.notifier.prompt("Dir Sync preview", message[:500])
            return

        self.notifier.success(f"Action '{action.name}' completed")

    def run_source_to_destination(self, action: SyncAction, soft_run: bool = False) -> None:
        output = self._run_one_way(action.src_path, action.dst_path, action, soft_run=soft_run)
        if soft_run:
            preview = output or f"Preview for '{action.name}' completed"
            self.notifier.prompt("Dir Sync preview", preview[:500])
            return
        self.notifier.success(f"Action '{action.name}' completed")

    def _run_one_way(
        self, src: str, dst: str, action: SyncAction, reverse: bool = False, soft_run: bool = False
    ) -> str:
        src_path = Path(src)
        dst_path = Path(dst)
        created_for_preview = False
        if soft_run and not dst_path.exists():
            dst_path.mkdir(parents=True, exist_ok=True)
            created_for_preview = True
        if not soft_run:
            dst_path.mkdir(parents=True, exist_ok=True)
        label = f"{action.name} ({'dst→src' if reverse else 'src→dst'})"
        try:
            if self.rsync_path:
                cmd = [
                    self.rsync_path,
                    "-avh",
                    "--delete",
                ]
                if soft_run:
                    cmd.extend(["--dry-run", "--stats"])
                for pattern in action.includes:
                    cmd.extend(["--include", pattern])
                for pattern in action.excludes:
                    cmd.extend(["--exclude", pattern])
                cmd.extend([f"{src_path}/", f"{dst_path}/"])
                return self._run_command(cmd, label, soft_run)
            if self.robocopy_path:
                cmd = [
                    "robocopy",
                    str(src_path),
                    str(dst_path),
                    "/MIR",
                ]
                if action.includes:
                    cmd.extend(action.includes)
                if action.excludes:
                    file_excludes: list[str] = []
                    dir_excludes: list[str] = []
                    for pattern in action.excludes:
                        if "/" in pattern or "\\" in pattern:
                            dir_excludes.append(pattern)
                        else:
                            file_excludes.append(pattern)
                    if file_excludes:
                        cmd.extend(["/XF"] + file_excludes)
                    if dir_excludes:
                        cmd.extend(["/XD"] + dir_excludes)
                if soft_run:
                    cmd.append("/L")
                return self._run_command(cmd, label, soft_run)

            if soft_run:
                return "Soft run not available without rsync/robocopy; install rsync to preview."
            self.logger.warning("rsync not available; falling back to shutil copy")
            self._python_copy(src_path, dst_path, action.includes, action.excludes)
            return ""
        finally:
            if created_for_preview:
                try:
                    dst_path.rmdir()
                except OSError:
                    pass

    def _run_command(self, cmd: Iterable[str], label: str, soft_run: bool = False) -> str:
        self.logger.info("Running %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.logger.error("Sync command failed: %s", result.stderr)
            self.notifier.error(f"{label} failed: {result.stderr.strip()[:200]}")
            alert(f"Sync failed for {label}: {result.stderr}")
            raise RuntimeError(result.stderr)
        if soft_run:
            return result.stdout.strip() or f"{label} dry run completed"
        return ""

    def _python_copy(
        self,
        src: Path,
        dst: Path,
        includes: List[str] | None = None,
        excludes: List[str] | None = None,
    ) -> None:
        def _matches(name: str, rel: str, patterns: List[str]) -> bool:
            return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in patterns)

        for item in src.rglob("*"):
            rel = item.relative_to(src).as_posix()
            if includes and not _matches(item.name, rel, includes):
                continue
            if excludes and _matches(item.name, rel, excludes):
                continue
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

    def _snapshot(self, root: Path) -> dict[str, tuple[int, str]]:
        snapshot: dict[str, tuple[int, str]] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = os.fspath(path.relative_to(root))
            stat = path.stat()
            snapshot[rel] = (stat.st_size, self._file_hash(path))
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
