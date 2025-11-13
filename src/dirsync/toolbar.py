from __future__ import annotations

import datetime as dt
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from .config import ConfigManager, SyncAction
from .constants import EXPORT_DIR
from .notifications import Notifier
from .sync import SyncExecutor
from .ui_config import ConfigWindow
from .ui_dialogs import alert


class ToolbarController:
    def __init__(
        self,
        manager: ConfigManager,
        executor: SyncExecutor,
        notifier: Notifier,
        on_config_change: Callable[[], None],
    ):
        self.manager = manager
        self.executor = executor
        self.notifier = notifier
        self.config_window = ConfigWindow(manager)
        self.on_config_change = on_config_change
        self.icon = pystray.Icon("dir-sync", self._create_image(), "Dir Sync", self._build_menu())

    def run(self):
        self.icon.run()

    def stop(self):
        self.icon.stop()

    def refresh(self):
        self.icon.menu = self._build_menu()
        self.icon.update_menu()
        self.on_config_change()

    def _build_menu(self):
        run_items = [
            pystray.MenuItem(action.name, self._make_runner(action))
            for action in self.manager.config.actions
        ]
        edit_items = [
            pystray.MenuItem(action.name, self._make_editor(action.name))
            for action in self.manager.config.actions
        ]
        placeholder = pystray.MenuItem("No actions", lambda icon, item: None, enabled=False)
        run_menu = pystray.Menu(*(run_items or [placeholder]))
        edit_menu = pystray.Menu(*(edit_items or [placeholder]))

        menu = pystray.Menu(
            pystray.MenuItem("Run", run_menu),
            pystray.MenuItem("Add new action", lambda icon, item: self._open_creator()),
            pystray.MenuItem("Modify action", edit_menu),
            pystray.MenuItem("Export", lambda icon, item: self._export_config()),
            pystray.MenuItem("Import", lambda icon, item: self._import_config()),
            pystray.MenuItem("Quit", lambda icon, item: self.stop()),
        )
        return menu

    def _make_runner(self, action: SyncAction) -> Callable:
        def _runner(icon, item):
            threading.Thread(target=self._run_action, args=(action,), daemon=True).start()

        return _runner

    def _make_editor(self, name: str) -> Callable:
        def _edit(icon, item):
            self.config_window.edit_action(name)
            self.refresh()

        return _edit

    def _open_creator(self):
        self.config_window.add_action()
        self.refresh()

    def _run_action(self, action: SyncAction):
        try:
            self.executor.run_action(action)
        except Exception as exc:  # pragma: no cover - surfaced via notification
            self.notifier.error(str(exc))

    def _export_config(self):
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        default = EXPORT_DIR / f"dir-sync-{dt.datetime.now():%Y%m%d-%H%M%S}.yml"
        root = tk.Tk()
        root.withdraw()
        target = filedialog.asksaveasfilename(
            initialdir=str(EXPORT_DIR),
            initialfile=default.name,
            defaultextension=".yml",
            filetypes=(("YAML", "*.yml"),),
        )
        root.destroy()
        if not target:
            return
        self.manager.export(Path(target))
        alert(f"Exported config to {target}")

    def _import_config(self):
        root = tk.Tk()
        root.withdraw()
        source = filedialog.askopenfilename(filetypes=(("YAML", "*.yml"),))
        root.destroy()
        if not source:
            return
        self.manager.import_file(Path(source))
        self.refresh()
        alert(f"Imported {source}")

    def _create_image(self):
        size = 32
        image = Image.new("RGB", (size, size), "#1f2937")
        draw = ImageDraw.Draw(image)
        draw.rectangle((6, 10, 26, 14), fill="#22d3ee")
        draw.rectangle((6, 18, 26, 22), fill="#f472b6")
        return image
