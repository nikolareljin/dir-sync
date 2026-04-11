from __future__ import annotations

import datetime as dt
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable, TypedDict

import pystray
from PIL import Image, ImageDraw

from .config import ConfigManager, SyncAction
from .constants import EXPORT_DIR
from .notifications import Notifier
from .sync import SyncExecutor
from .ui_config import ConfigWindow
from .ui_dialogs import alert


class ActionStatus(TypedDict):
    state: str
    ts: float


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
        self.soft_run_enabled = True
        self.action_status: dict[str, ActionStatus] = {}
        self.icon = pystray.Icon(
            "dir-sync", self._create_image(), "Dir Sync", menu=self._build_menu()
        )

    def run(self):
        self.icon.run(setup=self._setup_icon)

    def stop(self):
        self.icon.stop()

    def refresh(self):
        self.icon.menu = self._build_menu()
        self.icon.update_menu()
        self.on_config_change()

    def _setup_icon(self, icon: pystray.Icon):
        icon.menu = self._build_menu()
        icon.visible = True
        icon.update_menu()
        if not icon.HAS_MENU:
            self.notifier.error(
                "Tray backend has no menu support. Install AppIndicator/GTK tray packages."
            )

    def _build_menu(self):
        run_items = [
            pystray.MenuItem(action.name, self._make_runner(action, soft_run=None))
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
            pystray.MenuItem("Run configured", run_menu),
            pystray.MenuItem("Run all changed dirs", lambda icon, item: self._run_all_changed()),
            pystray.MenuItem("Add new action", lambda icon, item: self._open_creator()),
            pystray.MenuItem("Modify action", edit_menu),
            pystray.MenuItem("Export", lambda icon, item: self._export_config()),
            pystray.MenuItem("Import", lambda icon, item: self._import_config()),
            pystray.MenuItem("Quit", lambda icon, item: self.stop()),
        )
        return menu

    def _make_runner(self, action: SyncAction, soft_run: bool | None = None) -> Callable:
        def _runner(icon, item):
            effective_soft_run = self.soft_run_enabled if soft_run is None else soft_run
            threading.Thread(
                target=self._run_action, args=(action, effective_soft_run), daemon=True
            ).start()

        return _runner

    def _make_editor(self, name: str) -> Callable:
        def _edit(icon, item):
            self._edit_action(name)

        return _edit

    def _make_source_runner(self, action: SyncAction, soft_run: bool | None = None) -> Callable:
        def _runner(icon, item):
            effective_soft_run = self.soft_run_enabled if soft_run is None else soft_run
            threading.Thread(
                target=self._run_source_action, args=(action, effective_soft_run), daemon=True
            ).start()

        return _runner

    def _open_creator(self):
        self.config_window.add_action()
        self.refresh()

    def _edit_action(self, name: str):
        self.config_window.edit_action(name)
        self.refresh()

    def _toggle_soft_run(self, icon, item):
        self.soft_run_enabled = not self.soft_run_enabled
        self.icon.update_menu()

    def _is_soft_run_checked(self, item):
        return self.soft_run_enabled

    def _run_action(self, action: SyncAction, soft_run: bool):
        self._mark_status(action.name, "running")
        try:
            self.executor.run_action(action, soft_run=soft_run)
            self._mark_status(action.name, "done")
            self.refresh()
        except Exception as exc:  # pragma: no cover - surfaced via notification
            self.notifier.error(str(exc))
            self._mark_status(action.name, "error")

    def _run_source_action(self, action: SyncAction, soft_run: bool):
        self._mark_status(action.name, "running")
        try:
            self.executor.run_source_to_destination(action, soft_run=soft_run)
            self._mark_status(action.name, "done")
            self.refresh()
        except Exception as exc:  # pragma: no cover - surfaced via notification
            self.notifier.error(str(exc))
            self._mark_status(action.name, "error")

    def _mark_status(self, name: str, state: str):
        self.action_status[name] = {"state": state, "ts": time.time()}

    def _format_action_label(self, action: SyncAction) -> str:
        status = self.action_status.get(action.name, {})
        state = status.get("state", "idle")
        prefix = "   "
        if state == "running":
            spinner = "|/-\\"[int(time.time() * 4) % 4]
            prefix = f"[{spinner}]"
        elif state == "done":
            prefix = "[✔]"
        elif state == "error":
            prefix = "[!]"
        else:
            if not Path(action.dst_path).exists() or not Path(action.src_path).exists():
                prefix = "[!]"
        return f"{prefix} {action.name}"

    def _run_all_changed(self):
        threading.Thread(target=self._run_changed_thread, daemon=True).start()

    def _run_changed_thread(self):
        changed = self.executor.pending_actions(self.manager.config.actions)
        if not changed:
            self.notifier.success("No source changes detected")
            return
        for action in changed:
            self._run_source_action(action, soft_run=False)

    def _action_label(self, action: SyncAction) -> str:
        has_changes = self.executor.has_pending_source_changes(action)
        marker = "changes pending" if has_changes else "up-to-date"
        return f"{action.name} [{marker}]"

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
        try:
            self.manager.export(Path(target))
        except ValueError as exc:
            alert(str(exc))
            return
        alert(f"Exported config to {target}")

    def _import_config(self):
        root = tk.Tk()
        root.withdraw()
        source = filedialog.askopenfilename(filetypes=(("YAML", "*.yml"),))
        root.destroy()
        if not source:
            return
        try:
            self.manager.import_file(Path(source))
        except ValueError as exc:
            alert(str(exc))
            return
        self.refresh()
        alert(f"Imported {source}")

    def _create_image(self):
        size = 32
        image = Image.new("RGB", (size, size), "#1f2937")
        draw = ImageDraw.Draw(image)
        draw.rectangle((6, 10, 26, 14), fill="#22d3ee")
        draw.rectangle((6, 18, 26, 22), fill="#f472b6")
        return image
