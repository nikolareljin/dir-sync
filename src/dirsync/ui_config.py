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
        root.geometry("600x560")
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        tk.Label(root, text="Action name").grid(row=0, column=0, columnspan=2, sticky="w")
        name_var = tk.StringVar(value=action.name)
        name_entry = tk.Entry(root, textvariable=name_var)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)

        drives = self._available_mounts()

        # SRC pane
        src_frame = ttk.LabelFrame(root, text="Source")
        src_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        src_frame.grid_columnconfigure(0, weight=1)
        src_path_var = tk.StringVar(value=action.src_path)
        tk.Label(src_frame, text="Directory").grid(row=0, column=0, sticky="w")
        tk.Entry(src_frame, textvariable=src_path_var, width=30).grid(row=1, column=0, sticky="ew")
        tk.Button(src_frame, text="Browse", command=lambda: self._choose_dir(src_path_var)).grid(
            row=1, column=1
        )
        ttk.Label(src_frame, text="Select drive").grid(row=2, column=0, sticky="w", pady=(6, 0))
        src_drive_combo = ttk.Combobox(
            src_frame, textvariable=src_path_var, values=drives, state="readonly"
        )
        src_drive_combo.grid(row=3, column=0, columnspan=2, sticky="ew")

        # DST pane
        dst_frame = ttk.LabelFrame(root, text="Destination")
        dst_frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
        dst_frame.grid_columnconfigure(0, weight=1)
        dst_path_var = tk.StringVar(value=action.dst_path)
        tk.Label(dst_frame, text="Directory").grid(row=0, column=0, sticky="w")
        tk.Entry(dst_frame, textvariable=dst_path_var, width=30).grid(row=1, column=0, sticky="ew")
        tk.Button(dst_frame, text="Browse", command=lambda: self._choose_dir(dst_path_var)).grid(
            row=1, column=1
        )
        ttk.Label(dst_frame, text="Select drive").grid(row=2, column=0, sticky="w", pady=(6, 0))
        dst_drive_combo = ttk.Combobox(
            dst_frame, textvariable=dst_path_var, values=drives, state="readonly"
        )
        dst_drive_combo.grid(row=3, column=0, columnspan=2, sticky="ew")

        def populate_drive_fields():
            available = self._available_mounts()
            src_drive_combo["values"] = available
            dst_drive_combo["values"] = available
            if available:
                src_path_var.set(available[0])
                dst_path_var.set(available[-1])
                src_drive_combo.set(available[0])
                dst_drive_combo.set(available[-1])

        tk.Button(root, text="Detect Drives", command=populate_drive_fields).grid(
            row=3, column=0, sticky="w", padx=5
        )

        method_var = tk.StringVar(value=action.method)
        action_type_var = tk.StringVar(value=action.action_type)

        schedule_parts = (action.schedule or "").split()
        default_schedule = ["0", "0", "*", "*", "*"]
        builder_parts = schedule_parts[:5] if len(schedule_parts) >= 5 else default_schedule
        schedule_mode_var = tk.StringVar(
            value="builder" if len(schedule_parts) in (0, 5) else "custom"
        )
        schedule_var = tk.StringVar(value=action.schedule or " ".join(builder_parts))
        sched_min_var = tk.StringVar(value=builder_parts[0])
        sched_hour_var = tk.StringVar(value=builder_parts[1])
        sched_dom_var = tk.StringVar(value=builder_parts[2])
        sched_month_var = tk.StringVar(value=builder_parts[3])
        sched_dow_var = tk.StringVar(value=builder_parts[4])

        method_menu = ttk.OptionMenu(root, method_var, action.method, *SUPPORTED_METHODS)
        method_menu.grid(row=4, column=0, sticky="ew", padx=5)
        action_type_menu = ttk.OptionMenu(
            root,
            action_type_var,
            action.action_type,
            *SUPPORTED_ACTION_TYPES,
        )
        action_type_menu.grid(row=4, column=1, sticky="ew", padx=5)

        # Include / Exclude patterns
        filter_frame = ttk.LabelFrame(root, text="File filters (one glob pattern per line)")
        filter_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        filter_frame.grid_columnconfigure(0, weight=1)
        filter_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(filter_frame, text="Include patterns").grid(row=0, column=0, sticky="w", padx=4)
        includes_text = tk.Text(filter_frame, height=3, width=25)
        includes_text.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        includes_text.insert("1.0", "\n".join(action.includes))

        ttk.Label(filter_frame, text="Exclude patterns").grid(row=0, column=1, sticky="w", padx=4)
        excludes_text = tk.Text(filter_frame, height=3, width=25)
        excludes_text.grid(row=1, column=1, sticky="ew", padx=4, pady=(0, 4))
        excludes_text.insert("1.0", "\n".join(action.excludes))

        schedule_frame = ttk.LabelFrame(root, text="Schedule (cron)")
        schedule_frame.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        schedule_frame.grid_columnconfigure(0, weight=1)
        schedule_frame.grid_columnconfigure(1, weight=1)

        def _update_schedule_from_fields(*_args):
            if schedule_mode_var.get() != "builder":
                return
            parts = [
                sched_min_var.get() or "*",
                sched_hour_var.get() or "*",
                sched_dom_var.get() or "*",
                sched_month_var.get() or "*",
                sched_dow_var.get() or "*",
            ]
            schedule_var.set(" ".join(parts))

        def _sync_fields_from_schedule(expr: str):
            parts = expr.split()
            if len(parts) >= 5:
                sched_min_var.set(parts[0])
                sched_hour_var.set(parts[1])
                sched_dom_var.set(parts[2])
                sched_month_var.set(parts[3])
                sched_dow_var.set(parts[4])

        builder_radio = ttk.Radiobutton(
            schedule_frame,
            text="Use schedule builder",
            variable=schedule_mode_var,
            value="builder",
            command=lambda: _toggle_schedule_mode(),
        )
        builder_radio.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        custom_radio = ttk.Radiobutton(
            schedule_frame,
            text="Custom cron expression",
            variable=schedule_mode_var,
            value="custom",
            command=lambda: _toggle_schedule_mode(),
        )
        custom_radio.grid(row=0, column=1, sticky="w", padx=5, pady=(0, 5))

        builder_frame = ttk.Frame(schedule_frame)
        builder_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        for idx, (label, var) in enumerate(
            [
                ("Minute", sched_min_var),
                ("Hour", sched_hour_var),
                ("Day of month", sched_dom_var),
                ("Month", sched_month_var),
                ("Day of week", sched_dow_var),
            ]
        ):
            ttk.Label(builder_frame, text=label).grid(row=idx, column=0, sticky="w", pady=2)
            ttk.Entry(builder_frame, textvariable=var, width=20).grid(
                row=idx, column=1, sticky="ew", pady=2
            )
        builder_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(schedule_frame, text="Cron expression").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=5
        )
        custom_entry = ttk.Entry(schedule_frame, textvariable=schedule_var)
        custom_entry.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))

        for var in (sched_min_var, sched_hour_var, sched_dom_var, sched_month_var, sched_dow_var):
            var.trace_add("write", _update_schedule_from_fields)

        def _toggle_schedule_mode():
            if schedule_mode_var.get() == "builder":
                custom_entry.state(["disabled"])
                builder_frame.grid()
                _sync_fields_from_schedule(schedule_var.get())
                _update_schedule_from_fields()
            else:
                custom_entry.state(["!disabled"])
                builder_frame.grid_remove()

        _toggle_schedule_mode()

        def _set_schedule_enabled(enabled: bool):
            state = ["!disabled"] if enabled else ["disabled"]
            for widget in [builder_radio, custom_radio, custom_entry]:
                widget.state(state)
            for child in builder_frame.winfo_children():
                try:
                    child.state(state)
                except Exception:
                    pass

        def _toggle_schedule_visibility(*_args):
            is_scheduled = action_type_var.get() == "scheduled"
            _set_schedule_enabled(is_scheduled)
            if is_scheduled:
                _toggle_schedule_mode()

        action_type_var.trace_add("write", _toggle_schedule_visibility)
        _toggle_schedule_visibility()

        button_text = "Save"

        def _parse_patterns(text_widget: tk.Text) -> list[str]:
            raw = text_widget.get("1.0", "end").strip()
            return [line.strip() for line in raw.splitlines() if line.strip()]

        def on_submit():
            payload = SyncAction(
                name=name_var.get().strip(),
                src_path=src_path_var.get().strip(),
                dst_path=dst_path_var.get().strip(),
                method=method_var.get(),
                action_type=action_type_var.get(),
                schedule=(
                    schedule_var.get().strip() if action_type_var.get() == "scheduled" else None
                ),
                includes=_parse_patterns(includes_text),
                excludes=_parse_patterns(excludes_text),
            )
            if create:
                self.manager.config.add_action(payload)
            else:
                self.manager.config.update_action(payload)
            self.manager.save()
            root.destroy()

        def on_delete():
            if create:
                root.destroy()
                return
            self.manager.config.remove_action(action.name)
            self.manager.save()
            root.destroy()

        tk.Button(root, text=button_text, command=on_submit).grid(row=8, column=0, padx=5, pady=10)
        tk.Button(root, text="Cancel", command=root.destroy).grid(row=8, column=1, padx=5, pady=10)
        if not create:
            tk.Button(root, text="Delete", command=on_delete).grid(
                row=9, column=0, columnspan=2, padx=5, pady=(0, 10)
            )

        root.mainloop()

    def _choose_dir(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory(mustexist=False)
        if path:
            variable.set(path)

    def _available_mounts(self) -> list[str]:
        skip_mounts = {"/boot", "/boot/efi", "/home"}
        skip_prefixes = ("/proc/", "/sys/", "/dev/", "/run/", "/var/snap/")
        skip_types = {"proc", "sysfs", "tmpfs", "devtmpfs", "devfs", "overlay", "autofs"}
        drives = []
        for part in psutil.disk_partitions(all=True):
            if not part.mountpoint:
                continue
            if part.fstype and part.fstype.lower() in skip_types:
                continue
            mount = part.mountpoint.rstrip("/\\")
            if mount in skip_mounts:
                continue
            if any(mount.startswith(prefix.rstrip("/")) for prefix in skip_prefixes):
                continue
            drives.append(mount)
        return drives
