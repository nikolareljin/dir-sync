from __future__ import annotations

import copy
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, scrolledtext, ttk

import psutil

from .config import ConfigManager, SyncAction
from .constants import SUPPORTED_ACTION_TYPES, SUPPORTED_METHODS
from .detector import is_pseudo_mount, normalize_mountpoint
from .ui_dialogs import alert


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
        root.geometry("820x640")
        root.minsize(760, 580)

        self._configure_native_style(root)

        content = ttk.Frame(root, padding=(14, 12))
        content.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)

        ttk.Label(content, text="Action name").grid(row=0, column=0, columnspan=2, sticky="w")
        name_var = tk.StringVar(value=action.name)
        name_entry = ttk.Entry(content, textvariable=name_var)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        src_path_var = tk.StringVar(value=action.src_path)
        dst_path_var = tk.StringVar(value=action.dst_path)
        method_var = tk.StringVar(value=action.method)
        action_type_var = tk.StringVar(value=action.action_type)
        dst_device_id_var = tk.StringVar(value=action.dst_device_id or "")
        dst_path_on_device_var = tk.StringVar(value=action.dst_path_on_device or "")

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

        # SRC pane
        src_frame = ttk.LabelFrame(content, text="Source", padding=(10, 8))
        src_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=4)
        ttk.Label(src_frame, text="Directory").grid(row=0, column=0, sticky="w")
        ttk.Entry(src_frame, textvariable=src_path_var).grid(row=1, column=0, sticky="ew")
        ttk.Button(src_frame, text="Browse", command=lambda: self._choose_dir(src_path_var)).grid(
            row=1, column=1, padx=(6, 0)
        )
        src_frame.grid_columnconfigure(0, weight=1)

        # DST pane
        dst_frame = ttk.LabelFrame(content, text="Destination", padding=(10, 8))
        dst_frame.grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=4)
        ttk.Label(dst_frame, text="Directory").grid(row=0, column=0, sticky="w")
        ttk.Entry(dst_frame, textvariable=dst_path_var).grid(row=1, column=0, sticky="ew")
        ttk.Button(dst_frame, text="Browse", command=lambda: self._choose_dir(dst_path_var)).grid(
            row=1, column=1, padx=(6, 0)
        )
        ttk.Button(
            dst_frame,
            text="Create Dir",
            command=lambda: self._create_dir(dst_path_var),
        ).grid(row=1, column=2, padx=(6, 0))
        dst_frame.grid_columnconfigure(0, weight=1)

        def populate_drive_fields():
            available = self._available_mounts()
            if available:
                src_path_var.set(available[0])
                dst_path_var.set(available[-1])
            drives = list(psutil.disk_partitions(all=False))
            if drives:
                dst_device_id_var.set(drives[-1].device)

        button_row = ttk.Frame(content)
        button_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 6))
        button_row.grid_columnconfigure(0, weight=1)
        button_row.grid_columnconfigure(1, weight=1)

        ttk.Button(button_row, text="Detect Drives", command=populate_drive_fields).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            button_row,
            text="List USB IDs",
            command=lambda: self._open_usb_picker(root, dst_device_id_var, dst_path_var),
        ).grid(row=0, column=1, sticky="e")

        method_combo = ttk.Combobox(content, textvariable=method_var, values=SUPPORTED_METHODS)
        method_combo.state(["readonly"])
        method_combo.grid(row=4, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        action_type_combo = ttk.Combobox(
            content, textvariable=action_type_var, values=SUPPORTED_ACTION_TYPES
        )
        action_type_combo.state(["readonly"])
        action_type_combo.grid(row=4, column=1, sticky="ew", padx=(6, 0), pady=(0, 6))

        ttk.Label(content, text="Destination device ID (optional, for USB/HDD auto-match)").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )
        ttk.Entry(content, textvariable=dst_device_id_var).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(2, 8)
        )

        ttk.Label(content, text="Destination path on device (optional, e.g. backups/photos)").grid(
            row=7, column=0, columnspan=2, sticky="w"
        )
        ttk.Entry(content, textvariable=dst_path_on_device_var).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(2, 8)
        )

        filter_frame = ttk.LabelFrame(
            content,
            text="File filters (one glob pattern per line)",
            padding=(8, 6),
        )
        filter_frame.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(2, 6))
        filter_frame.grid_columnconfigure(0, weight=1)
        filter_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(filter_frame, text="Include patterns").grid(row=0, column=0, sticky="w", padx=4)
        includes_text = scrolledtext.ScrolledText(
            filter_frame,
            height=5,
            width=30,
            wrap=tk.NONE,
            font=tkfont.nametofont("TkTextFont"),
            borderwidth=1,
            relief=tk.SOLID,
        )
        includes_text.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        includes_text.insert("1.0", "\n".join(action.includes))

        ttk.Label(filter_frame, text="Exclude patterns").grid(row=0, column=1, sticky="w", padx=4)
        excludes_text = scrolledtext.ScrolledText(
            filter_frame,
            height=5,
            width=30,
            wrap=tk.NONE,
            font=tkfont.nametofont("TkTextFont"),
            borderwidth=1,
            relief=tk.SOLID,
        )
        excludes_text.grid(row=1, column=1, sticky="ew", padx=4, pady=(0, 4))
        excludes_text.insert("1.0", "\n".join(action.excludes))

        schedule_frame = ttk.LabelFrame(content, text="Schedule (cron)", padding=(8, 6))
        schedule_frame.grid(row=10, column=0, columnspan=2, sticky="nsew", pady=(2, 6))
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

        button_text = "Create" if create else "Save"

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
                dst_device_id=dst_device_id_var.get().strip() or None,
                dst_path_on_device=dst_path_on_device_var.get().strip() or None,
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

        action_buttons = ttk.Frame(content)
        action_buttons.grid(row=11, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(action_buttons, text=button_text, command=on_submit).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(action_buttons, text="Cancel", command=root.destroy).grid(row=0, column=1)
        if not create:
            ttk.Button(action_buttons, text="Delete", command=on_delete).grid(
                row=0, column=2, padx=(8, 0)
            )

        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        self._fit_window_to_content(root, min_width=760, min_height=580)
        root.mainloop()

    def _choose_dir(self, variable: tk.StringVar) -> None:
        path = filedialog.askdirectory(mustexist=False)
        if path:
            variable.set(path)

    def _create_dir(self, variable: tk.StringVar) -> None:
        path = variable.get().strip()
        if not path:
            alert("Destination path is empty. Enter a path first.")
            return
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            alert(f"Could not create directory:\n{path}\n\n{exc}")
            return
        alert(f"Directory is ready:\n{path}")

    def _open_usb_picker(
        self,
        parent: tk.Tk,
        dst_device_id_var: tk.StringVar,
        dst_path_var: tk.StringVar,
    ) -> None:
        drives = self._discover_drives()
        usb_drives = [drive for drive in drives if drive["removable"]]
        if not usb_drives:
            alert("No removable USB/HDD devices detected.")
            return

        dialog = tk.Toplevel(parent)
        dialog.title("Detected USB/HDD IDs")
        dialog.geometry("760x260")

        columns = ("volume_id", "device", "mountpoint")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=8)
        tree.heading("volume_id", text="Device ID")
        tree.heading("device", text="Device")
        tree.heading("mountpoint", text="Mountpoint")
        tree.column("volume_id", width=180)
        tree.column("device", width=180)
        tree.column("mountpoint", width=360)
        tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)

        for drive in usb_drives:
            tree.insert(
                "",
                "end",
                values=(drive["volume_id"], drive["device"], drive["mountpoint"]),
            )

        def apply_selected():
            selection = tree.selection()
            if not selection:
                return
            volume_id, _, mountpoint = tree.item(selection[0], "values")
            dst_device_id_var.set(volume_id)
            if not dst_path_var.get().strip():
                dst_path_var.set(mountpoint)
            dialog.destroy()

        ttk.Button(dialog, text="Use Selected", command=apply_selected).grid(
            row=1, column=0, sticky="w", padx=8, pady=8
        )
        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(
            row=1, column=1, sticky="e", padx=8, pady=8
        )

        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_columnconfigure(1, weight=1)

    def _available_mounts(self) -> list[str]:
        drives = []
        for part in psutil.disk_partitions(all=True):
            if not part.mountpoint:
                continue
            if is_pseudo_mount(part):
                continue
            drives.append(normalize_mountpoint(part.mountpoint))
        return drives

    def _discover_drives(self) -> list[dict[str, str | bool]]:
        discovered: list[dict[str, str | bool]] = []
        for part in psutil.disk_partitions(all=False):
            mountpoint = part.mountpoint.rstrip("/\\")
            device = part.device
            discovered.append(
                {
                    "mountpoint": mountpoint,
                    "device": device,
                    "volume_id": self._resolve_volume_id(device),
                    "removable": self._is_removable(device),
                }
            )
        return discovered

    def _resolve_volume_id(self, device: str) -> str:
        if not device:
            return ""
        by_uuid = Path("/dev/disk/by-uuid")
        resolved = Path(device).resolve()
        if by_uuid.exists():
            for entry in by_uuid.iterdir():
                try:
                    if entry.resolve() == resolved:
                        return entry.name
                except OSError:
                    continue
        return device

    def _is_removable(self, device: str) -> bool:
        if not device.startswith("/dev/"):
            return False

        leaf = Path(device).name
        candidates = [leaf]
        if leaf and leaf[-1].isdigit():
            candidates.append(leaf.rstrip("0123456789"))
            candidates.append(leaf.rstrip("0123456789p"))

        for name in candidates:
            sys_path = Path("/sys/class/block") / name / "removable"
            if not sys_path.exists():
                continue
            try:
                return sys_path.read_text(encoding="utf-8").strip() == "1"
            except OSError:
                return False
        return False

    def _fit_window_to_content(self, root: tk.Tk, min_width: int, min_height: int) -> None:
        root.update_idletasks()
        width = max(min_width, root.winfo_reqwidth() + 20)
        height = max(min_height, root.winfo_reqheight() + 20)
        root.geometry(f"{width}x{height}")

    def _configure_native_style(self, root: tk.Tk) -> None:
        style = ttk.Style(root)
        themes = style.theme_names()
        preferred_themes: list[str]
        if sys.platform.startswith("win"):
            preferred_themes = ["vista", "xpnative", "winnative", "default"]
        elif sys.platform == "darwin":
            preferred_themes = ["aqua", "default"]
        else:
            preferred_themes = ["default", "alt", "clam"]

        for theme in preferred_themes:
            if theme in themes:
                style.theme_use(theme)
                break

        default_font = tkfont.nametofont("TkDefaultFont")
        heading_font = default_font.copy()
        heading_font.configure(weight="bold")
        root.option_add("*Font", default_font)
        style.configure("TLabelframe.Label", font=heading_font)
