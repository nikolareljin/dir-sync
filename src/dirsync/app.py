from __future__ import annotations

import logging
from pathlib import Path

import typer

from .config import ConfigManager
from .detector import DriveDetector
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
        self.detector.watch_targets(destinations)
        self.scheduler.configure(self.manager.config.actions)

    def _handle_new_drive(self, mount: str) -> None:
        self.notifier.prompt("Drive detected", f"New device {mount} connected")
        if confirm(f"Create automation for {mount}?"):
            self.toolbar.config_window.add_action()
            self.toolbar.refresh()

    def _handle_known_drive(self, mount: str) -> None:
        matches = [
            action
            for action in self.manager.config.actions
            if self._normalize_path(action.dst_path).startswith(self._normalize_path(mount))
        ]
        for action in matches:
            if action.action_type == "auto_on_destination" or confirm(
                f"Run '{action.name}' for {mount}?"
            ):
                self.executor.run_action(action)

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
