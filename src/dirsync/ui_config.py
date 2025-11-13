from __future__ import annotations

import copy
import tkinter as tk
from tkinter import filedialog, ttk

import psutil

from .config import ConfigManager, SyncAction
from .constants import SUPPORTED_ACTION_TYPES, SUPPORTED_METHODS


class ConfigWindow:
    def __init__(self, manager: ConfigManager):
        self.manager = manager

    def add_action(self) -> None:
        action = SyncAction(
            name="new-action",
            src_path="",
            dst_path="",
            method="two_way",
            action_type="manual",
        )
        self._open(action, create=True)

    def edit_action(self, name: str) -> None:
        action = self.manager.config.find_action(name)
        if not action:
            return
        self._open(copy.deepcopy(action), create=False)

    def _open(self, action: SyncAction, create: bool) -> None:
        root = tk.Tk()
        root.title(f"Dir Sync - {action.name}")
        root.geometry("600x300")

        tk.Label(root, text="Action name").grid(row=0, column=0, columnspan=2, sticky="w")
        name_var = tk.StringVar(value=action.name)
        name_entry = tk.Entry(root, textvariable=name_var)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)

        # SRC pane
        src_frame = ttk.LabelFrame(root, text="Source")
        src_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        src_path_var = tk.StringVar(value=action.src_path)
        tk.Label(src_frame, text="Directory").grid(row=0, column=0, sticky="w")
        tk.Entry(src_frame, textvariable=src_path_var, width=30).grid(row=1, column=0, sticky="ew")
        tk.Button(src_frame, text="Browse", command=lambda: self._choose_dir(src_path_var)).grid(
            row=1, column=1
        )

        # DST pane
        dst_frame = ttk.LabelFrame(root, text="Destination")
        dst_frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
        dst_path_var = tk.StringVar(value=action.dst_path)
        tk.Label(dst_frame, text="Directory").grid(row=0, column=0, sticky="w")
        tk.Entry(dst_frame, textvariable=dst_path_var, width=30).grid(row=1, column=0, sticky="ew")
        tk.Button(dst_frame, text="Browse", command=lambda: self._choose_dir(dst_path_var)).grid(
            row=1, column=1
        )

        def populate_drive_fields():
            drives = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            if drives:
                src_path_var.set(drives[0])
                dst_path_var.set(drives[-1])

        tk.Button(root, text="Detect Drives", command=populate_drive_fields).grid(
            row=3, column=0, sticky="w", padx=5
        )

        method_var = tk.StringVar(value=action.method)
        action_type_var = tk.StringVar(value=action.action_type)
        schedule_var = tk.StringVar(value=action.schedule or "")

        method_menu = ttk.OptionMenu(root, method_var, action.method, *SUPPORTED_METHODS)
        method_menu.grid(row=4, column=0, sticky="ew", padx=5)
        action_type_menu = ttk.OptionMenu(
            root,
            action_type_var,
            action.action_type,
            *SUPPORTED_ACTION_TYPES,
        )
        action_type_menu.grid(row=4, column=1, sticky="ew", padx=5)

        tk.Label(root, text="Cron expression (for automated schedule)").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=5
        )
        tk.Entry(root, textvariable=schedule_var).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
        )

        button_text = "Create" if create else "Save"

        def on_submit():
            payload = SyncAction(
                name=name_var.get().strip(),
                src_path=src_path_var.get().strip(),
                dst_path=dst_path_var.get().strip(),
                method=method_var.get(),
                action_type=action_type_var.get(),
                schedule=schedule_var.get().strip() or None,
            )
            if create:
                self.manager.config.add_action(payload)
            else:
                self.manager.config.update_action(payload)
            self.manager.save()
            root.destroy()

        tk.Button(root, text=button_text, command=on_submit).grid(row=7, column=0, padx=5, pady=10)
        tk.Button(root, text="Cancel", command=root.destroy).grid(row=7, column=1, padx=5, pady=10)

        root.mainloop()

    def _choose_dir(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory()
        if path:
            variable.set(path)
