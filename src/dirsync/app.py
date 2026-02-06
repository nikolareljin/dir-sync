from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import typer

from .config import ConfigManager
from .detector import DriveDetector, MountedDrive
from .notifications import Notifier
from .scheduler import ActionScheduler
from .sync import SyncExecutor
from .toolbar import ToolbarController
from .ui_dialogs import confirm

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
cli = typer.Typer(help="Dir Sync toolbar app")


class DirSyncApp:
    def __init__(self):
        self.manager = ConfigManager()
        self.notifier = Notifier()
        self.executor = SyncExecutor(self.notifier)
        self.toolbar = ToolbarController(
            self.manager, self.executor, self.notifier, self._refresh_watchers
        )
        self.scheduler = ActionScheduler(self.executor.run_action)
        self.detector = DriveDetector(self._handle_new_drive, self._handle_known_drive)

    def start(self):
        self.manager.ensure_default()
        self._refresh_watchers()
        self.scheduler.configure(self.manager.config.actions)
        self.scheduler.start()
        self.detector.start()
        self.toolbar.run()

    def _refresh_watchers(self):
        destinations = {self._normalize_path(a.dst_path) for a in self.manager.config.actions}
        destination_ids = {
            action.dst_device_id for action in self.manager.config.actions if action.dst_device_id
        }
        self.detector.watch_targets(destinations, destination_ids)
        self.scheduler.configure(self.manager.config.actions)

    def _handle_new_drive(self, drive: MountedDrive) -> None:
        if not drive.is_removable:
            return
        self.notifier.prompt("Drive detected", f"New removable device {drive.mountpoint} connected")
        if confirm(
            f"Create automation for {drive.mountpoint}?\nDevice ID: {drive.volume_id or 'unknown'}"
        ):
            self.toolbar.config_window.add_action()
            self.toolbar.refresh()

    def _handle_known_drive(self, drive: MountedDrive) -> None:
        matches = [
            action
            for action in self.manager.config.actions
            if self._action_matches_drive(action, drive)
        ]
        for action in matches:
            resolved_action = self._resolve_action_for_mount(action, drive)
            if action.action_type == "auto_on_destination" or confirm(
                "Run rsync for this destination?\n"
                f"SRC: {action.src_path}\n"
                f"DST: {resolved_action.dst_path}\n"
                f"Action: {action.name}"
            ):
                self.executor.run_action(resolved_action)

    def _action_matches_drive(self, action, drive: MountedDrive) -> bool:
        if action.dst_device_id:
            return action.dst_device_id == drive.volume_id
        normalized_dst = self._normalize_path(action.dst_path)
        normalized_mount = self._normalize_path(drive.mountpoint)
        return normalized_dst.startswith(normalized_mount)

    def _resolve_action_for_mount(self, action, drive: MountedDrive):
        if not action.dst_device_id:
            return action
        if action.dst_path_on_device:
            return replace(action, dst_path=str(Path(drive.mountpoint) / action.dst_path_on_device))
        normalized_dst = self._normalize_path(action.dst_path)
        normalized_mount = self._normalize_path(drive.mountpoint)
        if normalized_dst.startswith(normalized_mount):
            return action
        subpath = Path(normalized_dst).name
        return replace(action, dst_path=str(Path(drive.mountpoint) / subpath))

    def _normalize_path(self, value: str) -> str:
        return str(Path(value).resolve()).rstrip("/\\")


@cli.command()
def run():  # pragma: no cover - UI entrypoint
    """Start the toolbar application."""
    app = DirSyncApp()
    app.start()


def main():  # pragma: no cover
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()
